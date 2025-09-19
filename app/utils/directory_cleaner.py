"""
Directory Cleaner для безопасного удаления файлов с системой бэкапов
"""
import os
import shutil
import json
import zipfile
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime
import tempfile
import logging

from .file_scanner import FileInfo, FileScanner


@dataclass
class BackupInfo:
    """Информация о бэкапе"""
    backup_id: str
    timestamp: str
    backup_path: str
    deleted_files: List[str]
    deleted_directories: List[str]
    total_files: int
    total_size: int


@dataclass
class CleanupOperation:
    """Информация об операции очистки"""
    operation_id: str
    timestamp: str
    files_to_delete: List[str]
    directories_to_delete: List[str]
    backup_created: bool
    backup_path: Optional[str] = None
    completed: bool = False
    errors: List[str] = None


@dataclass
class CleanupResult:
    """Результат операции очистки"""
    success: bool
    deleted_files: List[str]
    deleted_directories: List[str]
    space_freed: int
    backup_info: Optional[BackupInfo]
    errors: List[str]
    warnings: List[str]
    operation_id: str


class DirectoryCleaner:
    """Безопасная очистка директорий с системой бэкапов и отката"""
    
    def __init__(self, project_root: str, backup_dir: Optional[str] = None):
        """
        Инициализация очистителя
        
        Args:
            project_root: Корневая папка проекта
            backup_dir: Папка для бэкапов (по умолчанию temp)
        """
        self.project_root = Path(project_root).resolve()
        self.backup_dir = Path(backup_dir) if backup_dir else Path(tempfile.gettempdir()) / "ai_secretary_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # История операций
        self.operations_file = self.backup_dir / "cleanup_operations.json"
        self.operations_history: List[CleanupOperation] = self._load_operations_history()
    
    def clean_junk_files(self, junk_files: List[FileInfo], create_backup: bool = True) -> CleanupResult:
        """
        Очистка мусорных файлов
        
        Args:
            junk_files: Список мусорных файлов
            create_backup: Создавать ли бэкап перед удалением
            
        Returns:
            CleanupResult: Результат операции
        """
        operation_id = self._generate_operation_id()
        timestamp = datetime.now().isoformat()
        
        # Подготовка списков для удаления
        files_to_delete = [f.path for f in junk_files]
        directories_to_delete = self._find_empty_directories_after_cleanup(files_to_delete)
        
        # Валидация критически важных файлов
        validation_errors = self._validate_deletion_safety(files_to_delete + directories_to_delete)
        if validation_errors:
            return CleanupResult(
                success=False,
                deleted_files=[],
                deleted_directories=[],
                space_freed=0,
                backup_info=None,
                errors=validation_errors,
                warnings=[],
                operation_id=operation_id
            )
        
        # Создание операции
        operation = CleanupOperation(
            operation_id=operation_id,
            timestamp=timestamp,
            files_to_delete=files_to_delete,
            directories_to_delete=directories_to_delete,
            backup_created=create_backup,
            errors=[]
        )
        
        backup_info = None
        deleted_files = []
        deleted_directories = []
        space_freed = 0
        errors = []
        warnings = []
        
        try:
            # Создание бэкапа
            if create_backup:
                backup_info = self._create_backup(files_to_delete + directories_to_delete, operation_id)
                operation.backup_path = backup_info.backup_path
            
            # Удаление файлов
            for file_path in files_to_delete:
                try:
                    full_path = self.project_root / file_path
                    if full_path.exists() and full_path.is_file():
                        file_size = full_path.stat().st_size
                        full_path.unlink()
                        deleted_files.append(file_path)
                        space_freed += file_size
                        self.logger.info(f"Удален файл: {file_path}")
                except Exception as e:
                    error_msg = f"Ошибка при удалении файла {file_path}: {e}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            # Удаление пустых директорий
            for dir_path in directories_to_delete:
                try:
                    full_path = self.project_root / dir_path
                    if full_path.exists() and full_path.is_dir():
                        # Проверяем что директория действительно пуста
                        if not any(full_path.iterdir()):
                            full_path.rmdir()
                            deleted_directories.append(dir_path)
                            self.logger.info(f"Удалена пустая директория: {dir_path}")
                        else:
                            warnings.append(f"Директория {dir_path} не пуста, пропущена")
                except Exception as e:
                    error_msg = f"Ошибка при удалении директории {dir_path}: {e}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            operation.completed = True
            operation.errors = errors
            
        except Exception as e:
            error_msg = f"Критическая ошибка при очистке: {e}"
            errors.append(error_msg)
            self.logger.error(error_msg)
            operation.errors = errors
        
        finally:
            # Сохранение операции в историю
            self.operations_history.append(operation)
            self._save_operations_history()
        
        return CleanupResult(
            success=len(errors) == 0,
            deleted_files=deleted_files,
            deleted_directories=deleted_directories,
            space_freed=space_freed,
            backup_info=backup_info,
            errors=errors,
            warnings=warnings,
            operation_id=operation_id
        )
    
    def rollback_operation(self, operation_id: str) -> bool:
        """
        Откат операции очистки
        
        Args:
            operation_id: ID операции для отката
            
        Returns:
            bool: Успешность отката
        """
        # Поиск операции
        operation = None
        for op in self.operations_history:
            if op.operation_id == operation_id:
                operation = op
                break
        
        if not operation:
            self.logger.error(f"Операция {operation_id} не найдена")
            return False
        
        if not operation.backup_created or not operation.backup_path:
            self.logger.error(f"Для операции {operation_id} не создан бэкап")
            return False
        
        try:
            # Восстановление из бэкапа
            backup_path = Path(operation.backup_path)
            if not backup_path.exists():
                self.logger.error(f"Файл бэкапа {backup_path} не найден")
                return False
            
            # Распаковка бэкапа
            with zipfile.ZipFile(backup_path, 'r') as zip_file:
                zip_file.extractall(self.project_root)
            
            self.logger.info(f"Операция {operation_id} успешно откачена")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при откате операции {operation_id}: {e}")
            return False
    
    def _create_backup(self, paths_to_backup: List[str], operation_id: str) -> BackupInfo:
        """
        Создание бэкапа файлов и директорий
        
        Args:
            paths_to_backup: Пути для бэкапа
            operation_id: ID операции
            
        Returns:
            BackupInfo: Информация о созданном бэкапе
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{operation_id}_{timestamp}.zip"
        backup_path = self.backup_dir / backup_filename
        
        total_files = 0
        total_size = 0
        backed_up_files = []
        backed_up_dirs = []
        
        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for path_str in paths_to_backup:
                    full_path = self.project_root / path_str
                    
                    if not full_path.exists():
                        continue
                    
                    if full_path.is_file():
                        # Бэкап файла
                        zip_file.write(full_path, path_str)
                        total_files += 1
                        total_size += full_path.stat().st_size
                        backed_up_files.append(path_str)
                        
                    elif full_path.is_dir():
                        # Бэкап директории
                        for root, dirs, files in os.walk(full_path):
                            root_path = Path(root)
                            
                            # Добавляем саму директорию
                            rel_dir = root_path.relative_to(self.project_root)
                            zip_file.writestr(str(rel_dir) + '/', '')
                            
                            # Добавляем файлы в директории
                            for file in files:
                                file_path = root_path / file
                                rel_file_path = file_path.relative_to(self.project_root)
                                zip_file.write(file_path, str(rel_file_path))
                                total_files += 1
                                total_size += file_path.stat().st_size
                        
                        backed_up_dirs.append(path_str)
            
            backup_info = BackupInfo(
                backup_id=operation_id,
                timestamp=timestamp,
                backup_path=str(backup_path),
                deleted_files=backed_up_files,
                deleted_directories=backed_up_dirs,
                total_files=total_files,
                total_size=total_size
            )
            
            # Сохранение информации о бэкапе
            backup_info_path = self.backup_dir / f"backup_info_{operation_id}.json"
            with open(backup_info_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(backup_info), f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Создан бэкап: {backup_path} ({total_files} файлов, {total_size} байт)")
            return backup_info
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании бэкапа: {e}")
            raise
    
    def _validate_deletion_safety(self, paths: List[str]) -> List[str]:
        """
        Валидация безопасности удаления
        
        Args:
            paths: Пути для проверки
            
        Returns:
            List[str]: Список ошибок валидации
        """
        errors = []
        scanner = FileScanner(str(self.project_root))
        
        for path in paths:
            full_path = self.project_root / path
            
            # Проверка существования
            if not full_path.exists():
                continue
            
            # Проверка критически важных файлов
            if scanner._is_critical_file(Path(path)):
                errors.append(f"Попытка удаления критически важного файла: {path}")
            
            # Проверка что не удаляем корневые папки
            if len(Path(path).parts) == 1 and full_path.is_dir():
                if Path(path).name in ['app', 'migrations', 'scripts', 'docs']:
                    errors.append(f"Попытка удаления важной корневой папки: {path}")
            
            # Проверка прав доступа
            try:
                if full_path.is_file():
                    # Проверяем возможность записи в родительскую папку
                    if not os.access(full_path.parent, os.W_OK):
                        errors.append(f"Нет прав на удаление файла: {path}")
                elif full_path.is_dir():
                    # Проверяем возможность удаления директории
                    if not os.access(full_path, os.W_OK):
                        errors.append(f"Нет прав на удаление директории: {path}")
            except Exception as e:
                errors.append(f"Ошибка при проверке прав доступа для {path}: {e}")
        
        return errors
    
    def _find_empty_directories_after_cleanup(self, files_to_delete: List[str]) -> List[str]:
        """
        Поиск директорий, которые станут пустыми после удаления файлов
        
        Args:
            files_to_delete: Список файлов для удаления
            
        Returns:
            List[str]: Список директорий для удаления
        """
        directories_to_check = set()
        
        # Собираем все родительские директории удаляемых файлов
        for file_path in files_to_delete:
            parent = Path(file_path).parent
            while parent != Path('.'):
                directories_to_check.add(str(parent))
                parent = parent.parent
        
        empty_directories = []
        
        for dir_path in directories_to_check:
            full_dir_path = self.project_root / dir_path
            
            if not full_dir_path.exists() or not full_dir_path.is_dir():
                continue
            
            # Проверяем станет ли директория пустой
            remaining_items = []
            try:
                for item in full_dir_path.iterdir():
                    item_rel_path = str(item.relative_to(self.project_root))
                    if item_rel_path not in files_to_delete:
                        remaining_items.append(item)
                
                if not remaining_items:
                    empty_directories.append(dir_path)
                    
            except Exception as e:
                self.logger.warning(f"Ошибка при проверке директории {dir_path}: {e}")
        
        # Сортируем по глубине (сначала самые глубокие)
        empty_directories.sort(key=lambda x: len(Path(x).parts), reverse=True)
        
        return empty_directories
    
    def _generate_operation_id(self) -> str:
        """Генерация уникального ID операции"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"cleanup_{timestamp}_{len(self.operations_history)}"
    
    def _load_operations_history(self) -> List[CleanupOperation]:
        """Загрузка истории операций"""
        if not self.operations_file.exists():
            return []
        
        try:
            with open(self.operations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [CleanupOperation(**op) for op in data]
        except Exception as e:
            self.logger.warning(f"Ошибка при загрузке истории операций: {e}")
            return []
    
    def _save_operations_history(self):
        """Сохранение истории операций"""
        try:
            with open(self.operations_file, 'w', encoding='utf-8') as f:
                data = [asdict(op) for op in self.operations_history]
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении истории операций: {e}")
    
    def get_operations_history(self) -> List[CleanupOperation]:
        """Получение истории операций"""
        return self.operations_history.copy()
    
    def get_backup_info(self, operation_id: str) -> Optional[BackupInfo]:
        """
        Получение информации о бэкапе
        
        Args:
            operation_id: ID операции
            
        Returns:
            Optional[BackupInfo]: Информация о бэкапе или None
        """
        backup_info_path = self.backup_dir / f"backup_info_{operation_id}.json"
        
        if not backup_info_path.exists():
            return None
        
        try:
            with open(backup_info_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return BackupInfo(**data)
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке информации о бэкапе: {e}")
            return None
    
    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """
        Очистка старых бэкапов
        
        Args:
            keep_days: Количество дней для хранения бэкапов
            
        Returns:
            int: Количество удаленных бэкапов
        """
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            for backup_file in self.backup_dir.glob("backup_*.zip"):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    deleted_count += 1
                    
                    # Удаляем соответствующий info файл
                    info_file = self.backup_dir / backup_file.name.replace('.zip', '.json').replace('backup_', 'backup_info_')
                    if info_file.exists():
                        info_file.unlink()
            
            self.logger.info(f"Удалено {deleted_count} старых бэкапов")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Ошибка при очистке старых бэкапов: {e}")
            return 0