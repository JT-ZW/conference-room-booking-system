# PowerShell script to remove sensitive files from Git history
# WARNING: This rewrites Git history. Make sure to coordinate with your team!

Write-Host "🔐 Removing sensitive files from Git history..." -ForegroundColor Yellow
Write-Host "⚠️  WARNING: This will rewrite Git history!" -ForegroundColor Red
Write-Host "🔄 Make sure all team members are aware and have pushed their changes." -ForegroundColor Yellow

$confirmation = Read-Host "Do you want to continue? (y/N)"

if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
    Write-Host "🗑️  Removing .env file from Git history..." -ForegroundColor Green
    git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch .env' --prune-empty --tag-name-filter cat -- --all

    Write-Host "🗑️  Removing instance/ directory from Git history..." -ForegroundColor Green
    git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch -r instance/' --prune-empty --tag-name-filter cat -- --all

    Write-Host "🗑️  Removing virtual environment directories..." -ForegroundColor Green
    git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch -r central-reservations/' --prune-empty --tag-name-filter cat -- --all
    git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch -r reservations/' --prune-empty --tag-name-filter cat -- --all

    Write-Host "🧹 Cleaning up Git references..." -ForegroundColor Green
    Remove-Item -Recurse -Force .git/refs/original/ -ErrorAction SilentlyContinue
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive

    Write-Host "✅ Sensitive files removed from Git history!" -ForegroundColor Green
    Write-Host "🚀 Next steps:" -ForegroundColor Cyan
    Write-Host "   1. Force push to remote: git push origin --force --all" -ForegroundColor White
    Write-Host "   2. Force push tags: git push origin --force --tags" -ForegroundColor White
    Write-Host "   3. Tell team members to run: git pull --rebase" -ForegroundColor White
    Write-Host "   4. Consider rotating any exposed secrets" -ForegroundColor White
}
else {
    Write-Host "❌ Operation cancelled." -ForegroundColor Red
}
