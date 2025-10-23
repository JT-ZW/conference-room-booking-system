#!/usr/bin/env python3
"""
Version Compatibility Checker
Ensures deployed versions match development versions
"""

import sys
import importlib.metadata as metadata
from packaging import version

# Expected versions (from working local environment)
EXPECTED_VERSIONS = {
    'Flask': '3.1.1',
    'supabase': '2.16.0',
    'Flask-SQLAlchemy': '3.1.1',
    'Flask-WTF': '1.2.2',
    'reportlab': '4.4.2',
    'Werkzeug': '3.1.3',
    'WTForms': '3.2.1'
}

def check_versions():
    """Check if installed versions match expected versions"""
    print("🔍 Checking package versions for compatibility...")
    print("=" * 60)
    
    issues = []
    
    for package, expected_version in EXPECTED_VERSIONS.items():
        try:
            installed_version = metadata.version(package)
            
            if installed_version == expected_version:
                print(f"✅ {package}: {installed_version} (matches expected)")
            else:
                print(f"⚠️  {package}: {installed_version} (expected {expected_version})")
                issues.append(f"{package}: {installed_version} != {expected_version}")
                
        except metadata.PackageNotFoundError:
            print(f"❌ {package}: NOT INSTALLED")
            issues.append(f"{package}: not installed")
    
    print("=" * 60)
    
    if issues:
        print(f"⚠️  Found {len(issues)} version issues:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n💡 Recommendation: Update requirements.txt to match working local versions")
        return False
    else:
        print("✅ All package versions match expected versions!")
        return True

if __name__ == "__main__":
    success = check_versions()
    sys.exit(0 if success else 1)
