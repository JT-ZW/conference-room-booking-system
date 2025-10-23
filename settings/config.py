<<<<<<< HEAD
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Validate environment variables

def validate_environment():
    """Validate all required environment variables"""
    required_vars = {
        'SUPABASE_URL': os.environ.get('SUPABASE_URL'),
        'SUPABASE_ANON_KEY': os.environ.get('SUPABASE_ANON_KEY'),
    }
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        print(f"❌ {error_msg}")
        raise ValueError(error_msg)
    print("✅ All required environment variables are set")
    # Check optional but important variables
    service_key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not service_key:
        print("⚠️ WARNING: SUPABASE_SERVICE_KEY not set. Some operations may fail due to RLS.")
    else:
        print("✅ Service key available for admin operations")
    return True

validate_environment()

# Flask app config
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-key-change-in-production-' + str(datetime.now().timestamp()))
    SESSION_COOKIE_SECURE = False  # Set to False for now, will be handled later
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_REFRESH_EACH_REQUEST = True
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = False
    ACTIVITY_LOG_RETENTION_DAYS = int(os.environ.get('ACTIVITY_LOG_RETENTION_DAYS', 90))
    ACTIVITY_LOG_ENABLED = os.environ.get('ACTIVITY_LOG_ENABLED', 'true').lower() == 'true'

# Supabase config
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY') 
=======
"""
Configuration module for Rainbow Towers Conference Room Booking System.

This module provides comprehensive configuration management with:
- Environment-specific configurations
- Robust validation and error handling
- Security-focused settings
- Type hints and documentation
- Logging configuration
- Database settings management
"""

import os
import secrets
from datetime import timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path
from dotenv import load_dotenv


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors."""
    pass


class EnvironmentValidator:
    """Handles validation of environment variables and system requirements."""
    
    # Required environment variables for basic functionality
    REQUIRED_VARS = {
        'SUPABASE_URL': 'Supabase project URL',
        'SUPABASE_ANON_KEY': 'Supabase anonymous key for client operations',
    }
    
    # Optional but recommended environment variables
    RECOMMENDED_VARS = {
        'SUPABASE_SERVICE_KEY': 'Supabase service key for admin operations',
        'SECRET_KEY': 'Flask secret key for session security',
        'FLASK_ENV': 'Application environment (development/production)',
    }
    
    # Security-critical variables that should be set in production
    SECURITY_CRITICAL_VARS = {
        'SECRET_KEY': 'Application secret key',
        'SUPABASE_SERVICE_KEY': 'Database admin access key',
    }

    @classmethod
    def validate_environment(cls) -> Tuple[bool, List[str], List[str], List[str]]:
        """
        Validate all environment variables and return detailed results.
        
        Returns:
            Tuple containing:
            - bool: Whether all required variables are set
            - List[str]: Missing required variables
            - List[str]: Missing recommended variables  
            - List[str]: Security warnings
        """
        missing_required = []
        missing_recommended = []
        security_warnings = []
        
        # Check required variables
        for var, description in cls.REQUIRED_VARS.items():
            if not os.environ.get(var):
                missing_required.append(f"{var} ({description})")
        
        # Check recommended variables
        for var, description in cls.RECOMMENDED_VARS.items():
            if not os.environ.get(var):
                missing_recommended.append(f"{var} ({description})")
        
        # Check security-critical variables
        flask_env = os.environ.get('FLASK_ENV', 'development')
        if flask_env == 'production':
            for var, description in cls.SECURITY_CRITICAL_VARS.items():
                value = os.environ.get(var)
                if not value:
                    security_warnings.append(f"Missing {var} in production")
                elif var == 'SECRET_KEY' and (
                    value.startswith('fallback') or 
                    len(value) < 32 or 
                    value == 'dev-key-change-in-production'
                ):
                    security_warnings.append(f"Weak {var} detected in production")
        
        is_valid = len(missing_required) == 0
        return is_valid, missing_required, missing_recommended, security_warnings

    @classmethod
    def print_validation_results(cls) -> bool:
        """Print validation results in a user-friendly format."""
        is_valid, missing_required, missing_recommended, security_warnings = cls.validate_environment()
        
        print("🔍 Environment Configuration Validation")
        print("=" * 50)
        
        if is_valid:
            print("✅ All required environment variables are set")
        else:
            print("❌ Missing required environment variables:")
            for var in missing_required:
                print(f"   - {var}")
        
        if missing_recommended:
            print("\n⚠️  Missing recommended environment variables:")
            for var in missing_recommended:
                print(f"   - {var}")
        
        if security_warnings:
            print("\n🔒 Security warnings:")
            for warning in security_warnings:
                print(f"   - {warning}")
        
        # Environment info
        flask_env = os.environ.get('FLASK_ENV', 'development')
        print(f"\n📊 Environment: {flask_env}")
        print(f"🔑 Service key available: {'✅' if os.environ.get('SUPABASE_SERVICE_KEY') else '❌'}")
        
        if not is_valid:
            print("\n💡 To fix missing variables:")
            print("   1. Create/update your .env file")
            print("   2. Add the missing variables listed above")
            print("   3. Restart the application")
        
        return is_valid


class BaseConfig:
    """Base configuration class with common settings."""
    
    # Load environment variables
    load_dotenv()
    
    # Flask Core Settings
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or cls._generate_fallback_secret_key()
    
    # Session Configuration
    SESSION_COOKIE_SECURE: bool = False  # Will be overridden in production
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=2)
    SESSION_REFRESH_EACH_REQUEST: bool = True
    
    # CSRF Protection
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600  # 1 hour
    WTF_CSRF_SSL_STRICT: bool = False  # Will be overridden in production
    
    # Application Settings
    ACTIVITY_LOG_RETENTION_DAYS: int = int(os.environ.get('ACTIVITY_LOG_RETENTION_DAYS', '90'))
    ACTIVITY_LOG_ENABLED: bool = os.environ.get('ACTIVITY_LOG_ENABLED', 'true').lower() == 'true'
    
    # File Upload Settings
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB max file upload
    UPLOAD_FOLDER: str = os.environ.get('UPLOAD_FOLDER', 'uploads')
    
    # Email Configuration (if needed for notifications)
    MAIL_SERVER: Optional[str] = os.environ.get('MAIL_SERVER')
    MAIL_PORT: int = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS: bool = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME: Optional[str] = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD: Optional[str] = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER: Optional[str] = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Business Logic Settings
    DEFAULT_BOOKING_DURATION_HOURS: int = int(os.environ.get('DEFAULT_BOOKING_DURATION_HOURS', '2'))
    MAX_BOOKING_DURATION_HOURS: int = int(os.environ.get('MAX_BOOKING_DURATION_HOURS', '12'))
    BUSINESS_HOURS_START: int = int(os.environ.get('BUSINESS_HOURS_START', '6'))  # 6 AM
    BUSINESS_HOURS_END: int = int(os.environ.get('BUSINESS_HOURS_END', '23'))    # 11 PM
    
    # API Settings
    API_RATE_LIMIT: str = os.environ.get('API_RATE_LIMIT', '100 per hour')
    API_PAGINATION_DEFAULT: int = int(os.environ.get('API_PAGINATION_DEFAULT', '20'))
    API_PAGINATION_MAX: int = int(os.environ.get('API_PAGINATION_MAX', '100'))
    
    # Timezone Settings
    TIMEZONE: str = os.environ.get('TIMEZONE', 'UTC')
    
    @classmethod
    def _generate_fallback_secret_key(cls) -> str:
        """Generate a fallback secret key if none is provided."""
        import time
        timestamp = str(int(time.time()))
        random_key = secrets.token_urlsafe(32)
        return f"fallback-key-change-in-production-{timestamp}-{random_key}"
    
    @classmethod
    def init_app(cls, app) -> None:
        """Initialize the Flask application with this configuration."""
        # Validate environment on initialization
        is_valid, missing_required, missing_recommended, security_warnings = (
            EnvironmentValidator.validate_environment()
        )
        
        if not is_valid:
            EnvironmentValidator.print_validation_results()
            raise ConfigValidationError(
                f"Missing required environment variables: {', '.join(missing_required)}"
            )
        
        # Log configuration status
        if missing_recommended or security_warnings:
            EnvironmentValidator.print_validation_results()


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    
    DEBUG: bool = True
    TESTING: bool = False
    
    # Development-specific session settings
    SESSION_COOKIE_SECURE: bool = False
    WTF_CSRF_SSL_STRICT: bool = False
    
    # Development logging
    LOG_LEVEL: str = 'DEBUG'
    LOG_TO_STDOUT: bool = True
    
    # Development database settings
    DATABASE_QUERY_TIMEOUT: int = 30
    
    @classmethod
    def init_app(cls, app) -> None:
        super().init_app(app)
        print("🔧 Running in DEVELOPMENT mode")
        print("   - Debug mode enabled")
        print("   - Detailed logging enabled")
        print("   - Security restrictions relaxed")


class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    
    DEBUG: bool = False
    TESTING: bool = False
    
    # Production security settings
    SESSION_COOKIE_SECURE: bool = True
    WTF_CSRF_SSL_STRICT: bool = True
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=1)  # Shorter in production
    
    # Production logging
    LOG_LEVEL: str = 'INFO'
    LOG_TO_STDOUT: bool = False
    LOG_TO_FILE: bool = True
    LOG_FILE_PATH: str = 'logs/app.log'
    
    # Production database settings
    DATABASE_QUERY_TIMEOUT: int = 10
    
    # Production performance settings
    SEND_FILE_MAX_AGE_DEFAULT: int = 31536000  # 1 year cache for static files
    
    @classmethod
    def init_app(cls, app) -> None:
        super().init_app(app)
        
        # Additional production validation
        secret_key = os.environ.get('SECRET_KEY')
        if not secret_key or secret_key.startswith('fallback'):
            raise ConfigValidationError(
                "Production mode requires a proper SECRET_KEY environment variable"
            )
        
        print("🚀 Running in PRODUCTION mode")
        print("   - Security hardening enabled")
        print("   - Performance optimizations active")
        print("   - Detailed logging configured")


class TestingConfig(BaseConfig):
    """Testing environment configuration."""
    
    DEBUG: bool = True
    TESTING: bool = True
    
    # Testing-specific settings
    WTF_CSRF_ENABLED: bool = False  # Disable CSRF for easier testing
    SESSION_COOKIE_SECURE: bool = False
    
    # Fast settings for tests
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(minutes=5)
    ACTIVITY_LOG_ENABLED: bool = False  # Disable activity logging in tests
    
    # Test database settings
    DATABASE_QUERY_TIMEOUT: int = 5
    
    @classmethod
    def init_app(cls, app) -> None:
        super().init_app(app)
        print("🧪 Running in TESTING mode")
        print("   - CSRF protection disabled")
        print("   - Activity logging disabled")
        print("   - Fast timeout settings")


class SupabaseConfig:
    """Supabase-specific configuration and validation."""
    
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL')
        self.anon_key = os.environ.get('SUPABASE_ANON_KEY')
        self.service_key = os.environ.get('SUPABASE_SERVICE_KEY')
        
        # Validate Supabase configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate Supabase configuration."""
        if not self.url:
            raise ConfigValidationError("SUPABASE_URL environment variable is required")
        
        if not self.anon_key:
            raise ConfigValidationError("SUPABASE_ANON_KEY environment variable is required")
        
        # Validate URL format
        if not self.url.startswith('https://') or not '.supabase.co' in self.url:
            raise ConfigValidationError("SUPABASE_URL appears to be invalid")
        
        # Validate key formats (basic check)
        if len(self.anon_key) < 100:  # Supabase keys are typically much longer
            print("⚠️  WARNING: SUPABASE_ANON_KEY appears to be shorter than expected")
        
        if self.service_key and len(self.service_key) < 100:
            print("⚠️  WARNING: SUPABASE_SERVICE_KEY appears to be shorter than expected")
    
    @property
    def has_service_key(self) -> bool:
        """Check if service key is available for admin operations."""
        return bool(self.service_key)
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for debugging."""
        return {
            'url': self.url,
            'has_anon_key': bool(self.anon_key),
            'has_service_key': bool(self.service_key),
            'project_id': self.url.split('//')[1].split('.')[0] if self.url else None
        }


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> BaseConfig:
    """
    Get configuration class based on environment.
    
    Args:
        config_name: Configuration name ('development', 'production', 'testing')
                    If None, uses FLASK_ENV environment variable
    
    Returns:
        Configuration class instance
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    config_class = config.get(config_name, config['default'])
    return config_class


# Initialize Supabase configuration
try:
    supabase_config = SupabaseConfig()
    
    # Export for backwards compatibility
    SUPABASE_URL = supabase_config.url
    SUPABASE_ANON_KEY = supabase_config.anon_key
    SUPABASE_SERVICE_KEY = supabase_config.service_key
    
except ConfigValidationError as e:
    print(f"❌ Supabase configuration error: {e}")
    print("Please check your environment variables and try again.")
    # Set None values to prevent import errors, but app will fail to start
    SUPABASE_URL = None
    SUPABASE_ANON_KEY = None
    SUPABASE_SERVICE_KEY = None
    supabase_config = None


# Validate environment on import (can be disabled by setting SKIP_ENV_VALIDATION=true)
if not os.environ.get('SKIP_ENV_VALIDATION', '').lower() == 'true':
    if not EnvironmentValidator.print_validation_results():
        print("\n🔧 Set SKIP_ENV_VALIDATION=true to bypass this check during development")


# Export the main Config class for backwards compatibility
Config = get_config()


if __name__ == '__main__':
    """Run configuration validation when executed directly."""
    print("🔍 Rainbow Towers - Configuration Validation")
    print("=" * 60)
    
    # Test all configurations
    for env_name, config_class in config.items():
        if env_name == 'default':
            continue
            
        print(f"\n📋 Testing {env_name.upper()} configuration:")
        try:
            # Temporarily set environment
            original_env = os.environ.get('FLASK_ENV')
            os.environ['FLASK_ENV'] = env_name
            
            test_config = config_class()
            print(f"   ✅ {env_name} configuration is valid")
            
            # Restore original environment
            if original_env:
                os.environ['FLASK_ENV'] = original_env
            elif 'FLASK_ENV' in os.environ:
                del os.environ['FLASK_ENV']
                
        except Exception as e:
            print(f"   ❌ {env_name} configuration error: {e}")
    
    # Test Supabase configuration
    print(f"\n🗄️  Supabase Configuration:")
    if supabase_config:
        info = supabase_config.get_connection_info()
        print(f"   Project: {info['project_id']}")
        print(f"   URL: {info['url']}")
        print(f"   Anon Key: {'✅' if info['has_anon_key'] else '❌'}")
        print(f"   Service Key: {'✅' if info['has_service_key'] else '❌'}")
    else:
        print("   ❌ Supabase configuration failed")
    
    print(f"\n🎉 Configuration validation complete!")
>>>>>>> 095b69e2baeff84440be421321549fe1a01b5cda
