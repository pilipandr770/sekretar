"""Signal CLI service for managing Signal CLI installation and phone verification."""
import os
import json
import asyncio
import subprocess
import tempfile
import shutil
import zipfile
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from flask import current_app
from app.models import Channel, Tenant
from app.utils.database import db
import structlog

logger = structlog.get_logger()


class SignalCLIService:
    """Service for managing Signal CLI installation and operations."""
    
    def __init__(self):
        self.base_dir = Path("signal-cli")
        self.cli_path = None
        self.java_path = "java"  # Assume Java is in PATH
        self.accounts_dir = None
        self.is_installed = False
        
    def initialize(self):
        """Initialize Signal CLI service."""
        try:
            # Create base directory
            self.base_dir.mkdir(exist_ok=True)
            self.accounts_dir = self.base_dir / "accounts"
            self.accounts_dir.mkdir(exist_ok=True)
            
            # Check if Signal CLI is already installed
            if self._check_installation():
                self.is_installed = True
                logger.info("Signal CLI already installed", path=str(self.cli_path))
            else:
                logger.info("Signal CLI not found, installation required")
            
            return True
            
        except Exception as e:
            logger.error("Failed to initialize Signal CLI service", error=str(e))
            return False
    
    async def install_signal_cli(self, version: str = "latest") -> Tuple[bool, str]:
        """Download and install Signal CLI."""
        try:
            logger.info("Starting Signal CLI installation", version=version)
            
            # Get latest version if not specified
            if version == "latest":
                version = await self._get_latest_version()
                if not version:
                    return False, "Failed to get latest version"
            
            # Download Signal CLI
            download_url = f"https://github.com/AsamK/signal-cli/releases/download/v{version}/signal-cli-{version}.tar.gz"
            download_path = self.base_dir / f"signal-cli-{version}.tar.gz"
            
            logger.info("Downloading Signal CLI", url=download_url)
            
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Extract archive
            logger.info("Extracting Signal CLI")
            shutil.unpack_archive(str(download_path), str(self.base_dir))
            
            # Find extracted directory
            extracted_dir = None
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name.startswith("signal-cli-"):
                    extracted_dir = item
                    break
            
            if not extracted_dir:
                return False, "Failed to find extracted Signal CLI directory"
            
            # Set CLI path
            self.cli_path = extracted_dir / "bin" / "signal-cli"
            
            # Make executable (Unix-like systems)
            if os.name != 'nt':
                os.chmod(self.cli_path, 0o755)
            
            # Clean up download
            download_path.unlink()
            
            # Verify installation
            if await self._verify_installation():
                self.is_installed = True
                logger.info("Signal CLI installed successfully", version=version)
                return True, f"Signal CLI v{version} installed successfully"
            else:
                return False, "Installation verification failed"
            
        except Exception as e:
            logger.error("Failed to install Signal CLI", error=str(e))
            return False, f"Installation failed: {str(e)}"
    
    async def register_phone_number(self, phone_number: str, captcha: str = None) -> Tuple[bool, str]:
        """Register a phone number with Signal."""
        if not self.is_installed:
            return False, "Signal CLI not installed"
        
        try:
            logger.info("Registering phone number", phone_number=phone_number)
            
            cmd = [
                self.java_path, "-jar", str(self.cli_path),
                "-a", phone_number,
                "register"
            ]
            
            if captcha:
                cmd.extend(["--captcha", captcha])
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                logger.info("Phone number registration initiated", phone_number=phone_number)
                return True, "Registration SMS sent. Please check your phone for verification code."
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error("Phone number registration failed", 
                           phone_number=phone_number, error=error_msg)
                
                # Check for specific error cases
                if "captcha" in error_msg.lower():
                    return False, "Captcha required. Please solve captcha and try again."
                elif "rate limit" in error_msg.lower():
                    return False, "Rate limited. Please wait before trying again."
                else:
                    return False, f"Registration failed: {error_msg}"
            
        except Exception as e:
            logger.error("Error registering phone number", 
                        phone_number=phone_number, error=str(e))
            return False, f"Registration error: {str(e)}"
    
    async def verify_phone_number(self, phone_number: str, verification_code: str) -> Tuple[bool, str]:
        """Verify phone number with SMS code."""
        if not self.is_installed:
            return False, "Signal CLI not installed"
        
        try:
            logger.info("Verifying phone number", phone_number=phone_number)
            
            cmd = [
                self.java_path, "-jar", str(self.cli_path),
                "-a", phone_number,
                "verify", verification_code
            ]
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                logger.info("Phone number verified successfully", phone_number=phone_number)
                
                # Create account directory
                account_dir = self.accounts_dir / phone_number.replace("+", "")
                account_dir.mkdir(exist_ok=True)
                
                return True, "Phone number verified successfully. Signal account is ready."
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error("Phone number verification failed", 
                           phone_number=phone_number, error=error_msg)
                
                if "invalid" in error_msg.lower():
                    return False, "Invalid verification code. Please check and try again."
                elif "expired" in error_msg.lower():
                    return False, "Verification code expired. Please request a new one."
                else:
                    return False, f"Verification failed: {error_msg}"
            
        except Exception as e:
            logger.error("Error verifying phone number", 
                        phone_number=phone_number, error=str(e))
            return False, f"Verification error: {str(e)}"
    
    async def send_message(self, phone_number: str, recipient: str, message: str, 
                          attachments: List[str] = None) -> Tuple[bool, str]:
        """Send a message via Signal."""
        if not self.is_installed:
            return False, "Signal CLI not installed"
        
        if not await self._is_account_registered(phone_number):
            return False, "Phone number not registered or verified"
        
        try:
            cmd = [
                self.java_path, "-jar", str(self.cli_path),
                "-a", phone_number,
                "send",
                "-m", message,
                recipient
            ]
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    if os.path.exists(attachment):
                        cmd.extend(["-a", attachment])
            
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                logger.info("Message sent successfully", 
                           phone_number=phone_number, recipient=recipient)
                return True, "Message sent successfully"
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error("Failed to send message", 
                           phone_number=phone_number, recipient=recipient, error=error_msg)
                return False, f"Failed to send message: {error_msg}"
            
        except Exception as e:
            logger.error("Error sending message", 
                        phone_number=phone_number, recipient=recipient, error=str(e))
            return False, f"Send error: {str(e)}"
    
    async def receive_messages(self, phone_number: str, timeout: int = 5) -> Tuple[bool, List[Dict]]:
        """Receive messages for a phone number."""
        if not self.is_installed:
            return False, []
        
        if not await self._is_account_registered(phone_number):
            return False, []
        
        try:
            cmd = [
                self.java_path, "-jar", str(self.cli_path),
                "-a", phone_number,
                "receive",
                "--json",
                "--timeout", str(timeout)
            ]
            
            result = await self._run_command(cmd, timeout=timeout + 5)
            
            messages = []
            if result.returncode == 0 and result.stdout:
                # Parse JSON messages
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            message_data = json.loads(line)
                            messages.append(message_data)
                        except json.JSONDecodeError:
                            continue
            
            return True, messages
            
        except Exception as e:
            logger.error("Error receiving messages", 
                        phone_number=phone_number, error=str(e))
            return False, []
    
    async def get_account_info(self, phone_number: str) -> Dict[str, Any]:
        """Get account information."""
        if not self.is_installed:
            return {"error": "Signal CLI not installed"}
        
        try:
            # Check if account is registered
            is_registered = await self._is_account_registered(phone_number)
            
            account_info = {
                "phone_number": phone_number,
                "is_registered": is_registered,
                "account_dir": str(self.accounts_dir / phone_number.replace("+", "")),
                "cli_version": await self._get_cli_version()
            }
            
            if is_registered:
                # Get additional account details
                cmd = [
                    self.java_path, "-jar", str(self.cli_path),
                    "-a", phone_number,
                    "listIdentities"
                ]
                
                result = await self._run_command(cmd)
                if result.returncode == 0:
                    account_info["identities"] = result.stdout.strip()
            
            return account_info
            
        except Exception as e:
            logger.error("Error getting account info", 
                        phone_number=phone_number, error=str(e))
            return {"error": str(e)}
    
    async def list_accounts(self) -> List[str]:
        """List all registered accounts."""
        if not self.is_installed:
            return []
        
        try:
            cmd = [self.java_path, "-jar", str(self.cli_path), "listAccounts"]
            result = await self._run_command(cmd)
            
            accounts = []
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and line.startswith('+'):
                        accounts.append(line)
            
            return accounts
            
        except Exception as e:
            logger.error("Error listing accounts", error=str(e))
            return []
    
    def get_installation_status(self) -> Dict[str, Any]:
        """Get Signal CLI installation status."""
        return {
            "is_installed": self.is_installed,
            "cli_path": str(self.cli_path) if self.cli_path else None,
            "base_dir": str(self.base_dir),
            "accounts_dir": str(self.accounts_dir),
            "java_available": self._check_java(),
            "version": asyncio.run(self._get_cli_version()) if self.is_installed else None
        }
    
    async def _get_latest_version(self) -> Optional[str]:
        """Get latest Signal CLI version from GitHub."""
        try:
            response = requests.get(
                "https://api.github.com/repos/AsamK/signal-cli/releases/latest",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            version = data["tag_name"].lstrip("v")
            return version
            
        except Exception as e:
            logger.error("Failed to get latest version", error=str(e))
            return None
    
    def _check_installation(self) -> bool:
        """Check if Signal CLI is installed."""
        try:
            # Look for signal-cli in base directory
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name.startswith("signal-cli-"):
                    cli_path = item / "bin" / "signal-cli"
                    if cli_path.exists():
                        self.cli_path = cli_path
                        return True
            
            return False
            
        except Exception:
            return False
    
    async def _verify_installation(self) -> bool:
        """Verify Signal CLI installation."""
        try:
            if not self.cli_path or not self.cli_path.exists():
                return False
            
            # Check Java availability
            if not self._check_java():
                return False
            
            # Test Signal CLI
            cmd = [self.java_path, "-jar", str(self.cli_path), "--version"]
            result = await self._run_command(cmd, timeout=10)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _check_java(self) -> bool:
        """Check if Java is available."""
        try:
            result = subprocess.run(
                [self.java_path, "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def _get_cli_version(self) -> Optional[str]:
        """Get Signal CLI version."""
        if not self.is_installed:
            return None
        
        try:
            cmd = [self.java_path, "-jar", str(self.cli_path), "--version"]
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return None
            
        except Exception:
            return None
    
    async def _is_account_registered(self, phone_number: str) -> bool:
        """Check if account is registered."""
        try:
            accounts = await self.list_accounts()
            return phone_number in accounts
        except Exception:
            return False
    
    async def _run_command(self, cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8', errors='ignore') if stdout else '',
                stderr=stderr.decode('utf-8', errors='ignore') if stderr else ''
            )
            
        except asyncio.TimeoutError:
            logger.error("Command timed out", cmd=' '.join(cmd))
            raise
        except Exception as e:
            logger.error("Error running command", cmd=' '.join(cmd), error=str(e))
            raise


# Global service instance
signal_cli_service = SignalCLIService()


def init_signal_cli_service(app):
    """Initialize Signal CLI service with Flask app."""
    try:
        success = signal_cli_service.initialize()
        if success:
            logger.info("Signal CLI service initialized successfully")
        else:
            logger.warning("Signal CLI service initialization failed")
        
        return signal_cli_service
        
    except Exception as e:
        logger.error("Failed to initialize Signal CLI service", error=str(e))
        return None


def get_signal_cli_service() -> SignalCLIService:
    """Get Signal CLI service instance."""
    return signal_cli_service