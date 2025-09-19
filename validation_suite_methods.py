"""
Additional methods for ValidationSuite class
"""

def run_comprehensive_validation(self) -> ValidationSuiteResult:
    """
    Run comprehensive validation of the entire project.
    
    Returns:
        ValidationSuiteResult with complete validation results
    """
    start_time = time.time()
    self.logger.info("🚀 Starting comprehensive project validation...")
    
    try:
        # 1. Configuration validation
        self.logger.info("📋 Running configuration validation...")
        self._run_config_validation()
        
        # 2. Health validation (if config is valid)
        if self.result.config_validation and self.result.config_validation.valid:
            self.logger.info("🏥 Running health validation...")
            self._run_health_validation()
        else:
            self.logger.warning("⚠️ Skipping health validation due to config issues")
        
        # 3. Route validation
        self.logger.info("🛣️ Running route validation...")
        self._run_route_validation()
        
        # 4. Gitignore validation
        self.logger.info("📁 Running gitignore validation...")
        self._run_gitignore_validation()
        
        # 5. Application startup test
        self.logger.info("🔄 Testing application startup...")
        self._test_application_startup()
        
        # 6. API endpoints test (if startup successful)
        if self.result.startup_test and self.result.startup_test.get('success'):
            self.logger.info("🌐 Testing API endpoints...")
            self._test_api_endpoints()
        else:
            self.logger.warning("⚠️ Skipping API tests due to startup issues")
        
        # 7. Generate final assessment
        self._generate_final_assessment()
        
    except Exception as e:
        self.logger.error(f"❌ Validation suite failed: {e}")
        self.result.errors.append(f"Validation suite failed: {e}")
        self.result.success = False
    
    finally:
        self.result.duration = time.time() - start_time
        self.logger.info(f"✅ Validation completed in {self.result.duration:.2f}s")
    
    return self.result

def _run_config_validation(self):
    """Run configuration validation."""
    try:
        validator = ConfigValidator(self.config_file)
        self.result.config_validation = validator.validate_all()
        
        if self.result.config_validation.valid:
            self.logger.info("✅ Configuration validation passed")
        else:
            self.logger.error("❌ Configuration validation failed")
            self.result.success = False
            
    except Exception as e:
        self.logger.error(f"❌ Config validation failed: {e}")
        self.result.errors.append(f"Config validation failed: {e}")
        self.result.success = False