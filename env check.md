# Check .gitignore has .env in it
cat .gitignore | grep .env

# Confirm .env is not being tracked
git ls-files | grep .env