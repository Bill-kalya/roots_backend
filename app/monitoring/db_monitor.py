from sqlalchemy import text
from typing import Dict, Any
import logging
from app.db.session import db_manager

logger = logging.getLogger(__name__)

class DatabaseMonitor:
    """Monitor database performance and health"""
    
    @staticmethod
    async def get_database_stats() -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}
        
        async with db_manager.get_read_session() as session:
            # Database size
            result = await session.execute(text("""
                SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb
            """))
            stats["size_mb"] = result.scalar()
            
            # Active connections
            result = await session.execute(text("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE datname = current_database()
            """))
            stats["active_connections"] = result.scalar()
            
            # Table sizes
            result = await session.execute(text("""
                SELECT 
                    tablename,
                    pg_total_relation_size(quote_ident(tablename)) / 1024 / 1024 as size_mb
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY size_mb DESC
            """))
            stats["table_sizes"] = [{"table": r[0], "size_mb": r[1]} for r in result.fetchall()]
            
            # Query statistics (slow queries)
            result = await session.execute(text("""
                SELECT 
                    query,
                    calls,
                    total_exec_time / 1000 as total_seconds,
                    mean_exec_time as avg_ms
                FROM pg_stat_statements
                ORDER BY total_exec_time DESC
                LIMIT 10
            """))
            stats["slow_queries"] = [{
                "query": r[0][:100],
                "calls": r[1],
                "total_seconds": round(r[2], 2),
                "avg_ms": round(r[3], 2)
            } for r in result.fetchall()]
        
        return stats
    
    @staticmethod
    async def get_cache_hit_ratio() -> Dict[str, float]:
        """Get cache hit ratios"""
        async with db_manager.get_read_session() as session:
            result = await session.execute(text("""
                SELECT 
                    sum(heap_blks_hit) / nullif(sum(heap_blks_hit + heap_blks_read),0) as table_hit_ratio,
                    sum(idx_blks_hit) / nullif(sum(idx_blks_hit + idx_blks_read),0) as index_hit_ratio
                FROM pg_statio_user_tables
            """))
            row = result.fetchone()
            
            return {
                "table_cache_hit_ratio": round(row[0] * 100, 2) if row[0] else 0,
                "index_cache_hit_ratio": round(row[1] * 100, 2) if row[1] else 0
            }