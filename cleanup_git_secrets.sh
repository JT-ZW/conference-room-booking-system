#!/bin/bash

# Script to remove sensitive files from Git history
# WARNING: This rewrites Git history. Make sure to coordinate with your team!

echo "🔐 Removing sensitive files from Git history..."
echo "⚠️  WARNING: This will rewrite Git history!"
echo "🔄 Make sure all team members are aware and have pushed their changes."
read -p "Do you want to continue? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing .env file from Git history..."
    git filter-branch --force --index-filter \
        'git rm --cached --ignore-unmatch .env' \
        --prune-empty --tag-name-filter cat -- --all

    echo "🗑️  Removing instance/ directory from Git history..."
    git filter-branch --force --index-filter \
        'git rm --cached --ignore-unmatch -r instance/' \
        --prune-empty --tag-name-filter cat -- --all

    echo "🗑️  Removing virtual environment directories..."
    git filter-branch --force --index-filter \
        'git rm --cached --ignore-unmatch -r central-reservations/' \
        --prune-empty --tag-name-filter cat -- --all

    git filter-branch --force --index-filter \
        'git rm --cached --ignore-unmatch -r reservations/' \
        --prune-empty --tag-name-filter cat -- --all

    echo "🧹 Cleaning up Git references..."
    rm -rf .git/refs/original/
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive

    echo "✅ Sensitive files removed from Git history!"
    echo "🚀 Next steps:"
    echo "   1. Force push to remote: git push origin --force --all"
    echo "   2. Force push tags: git push origin --force --tags"
    echo "   3. Tell team members to run: git pull --rebase"
    echo "   4. Consider rotating any exposed secrets"
else
    echo "❌ Operation cancelled."
fi
