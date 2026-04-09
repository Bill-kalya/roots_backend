import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class BackupService:
    """Enterprise database backup service"""
    
    def __init__(self):
        self.backup_path = Path(settings.BACKUP_PATH)
        self.backup_path.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self) -> Dict[str, Any]:
        """Create database backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_path / f"roots_backup_{timestamp}.sql"
        
        try:
            # Extract database connection details
            db_url = str(settings.DATABASE_URL)
            # Parse URL (simplified - use proper parsing in production)
            
            # Run pg_dump
            cmd = [
                "pg_dump",
                "--dbname", db_url,
                "--format", "custom",
                "--file", str(backup_file),
                "--verbose"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Compress backup
                compressed_file = backup_file.with_suffix('.sql.gz')
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                backup_file.unlink()  # Remove uncompressed
                
                # Clean old backups
                await self.cleanup_old_backups()
                
                return {
                    "success": True,
                    "file": str(compressed_file),
                    "size": compressed_file.stat().st_size,
                    "timestamp": timestamp
                }
            else:
                logger.error(f"Backup failed: {stderr.decode()}")
                return {
                    "success": False,
                    "error": stderr.decode()
                }
                
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return {"success": False, "error": str(e)}
    
    async def restore_backup(self, backup_file: Path) -> bool:
        """Restore database from backup"""
        try:
            cmd = [
                "pg_restore",
                "--dbname", str(settings.DATABASE_URL),
                "--clean",
                "--if-exists",
                "--no-owner",
                str(backup_file)
            ]
            
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()
            
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return False
    
    async def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        retention_date = datetime.now() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
        
        for backup_file in self.backup_path.glob("roots_backup_*.sql.gz"):
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_time < retention_date:
                backup_file.unlink()
                logger.info(f"Deleted old backup: {backup_file}")
    
    async def list_backups(self) -> list:
        """List available backups"""
        backups = []
        for backup_file in sorted(self.backup_path.glob("roots_backup_*.sql.gz"), reverse=True):
            backups.append({
                "file": backup_file.name,
                "size": backup_file.stat().st_size,
                "created": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
            })
        return backups