"""
Cleanup Manager для управления процессом очистки проекта
"""
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from .file_scanner import FileScanner, ScanResult, FileInfo
from .directory_cleaner import DirectoryCleaner, CleanupResult


@dataclass
class ProjectOptimizationResult:
    """Результат оптимизации структуры проекта"""
    scan_result: ScanResult
    cleanup_result: CleanupResult
    optimization_summary: Dict[str, any]
    recommendations: List[str]


class CleanupManager:
    """Менеджер для комплексной очистки и оптимизации проекта"""
    
    # Специфичные папки для удаления согласно требованиям
    SPECIFIC_DIRECTORIES_TO_REMOVE = [
        'test_execution_logs',
        'test_execution_traces', 
        'evidence',
        'examples'
    ]
    
    # Паттерны для final_reports (оставляем только последний)
    FINAL_REPORTS_DIR = 'final_reports'
    
    # Временные .db файлы в корне для удаления
    TEMP_DB_FILES = [
        'test.db',
        'dev.db', 
        'ai_secretary.db',  # в корне, не в instance
        'test_auth.db'
    ]
    
    # Дублирующиеся .env файлы
    DUPLICATE_ENV_FILES = [
        '.env.local',
        '.env.development', 
        '.env.production',
        '.env.test'
    ]
    
    def __init__(self, project_root: str, backup_dir: Optional[str] = None):
        """
        Инициализация менеджера очистки
        
        Args:
            project_root: Корневая папка проекта
            backup_dir: Папка для бэкапов
        """
        self.project_root = Path(project_root).resolve()
        self.scanner = FileScanner(str(self.project_root))
        self.cleaner = DirectoryCleaner(str(self.project_root), backup_dir)
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
    def analyze_project(self) -> ScanResult:
        """
        Анализ проекта для определения файлов для очистки
        
        Returns:
            ScanResult: Результат сканирования
        """
        self.logger.info("Начинаем анализ проекта...")
        scan_result = self.scanner.scan_project()
        
        # Логирование результатов
        summary = self.scanner.get_junk_summary(scan_result)
        self.logger.info(f"Найдено {summary['total_junk_files']} мусорных файлов "
                        f"({summary['junk_size_mb']} MB)")
        
        return scan_result
    
    def optimize_project_structure(self, create_backup: bool = True) -> ProjectOptimizationResult:
        """
        Комплексная оптимизация структуры проекта
        
        Args:
            create_backup: Создавать ли бэкап перед удалением
            
        Returns:
            ProjectOptimizationResult: Результат оптимизации
        """
        self.logger.info("Начинаем оптимизацию структуры проекта...")
        
        # 1. Анализ проекта
        scan_result = self.analyze_project()
        
        # 2. Добавление специфичных файлов и папок для удаления
        additional_junk = self._identify_specific_cleanup_targets()
        
        # 3. Объединение всех файлов для удаления
        all_junk_files = scan_result.junk_files + additional_junk
        
        # 4. Выполнение очистки
        cleanup_result = self.cleaner.clean_junk_files(all_junk_files, create_backup)
        
        # 5. Специальная обработка final_reports
        self._cleanup_final_reports()
        
        # 6. Создание сводки оптимизации
        optimization_summary = self._create_optimization_summary(scan_result, cleanup_result)
        
        # 7. Генерация рекомендаций
        recommendations = self._generate_recommendations(scan_result, cleanup_result)
        
        self.logger.info(f"Оптимизация завершена. Освобождено {cleanup_result.space_freed} байт")
        
        return ProjectOptimizationResult(
            scan_result=scan_result,
            cleanup_result=cleanup_result,
            optimization_summary=optimization_summary,
            recommendations=recommendations
        )
    
    def _identify_specific_cleanup_targets(self) -> List[FileInfo]:
        """
        Идентификация специфичных файлов и папок для удаления согласно требованиям
        
        Returns:
            List[FileInfo]: Дополнительные файлы для удаления
        """
        additional_junk = []
        
        # 1. Специфичные директории
        for dir_name in self.SPECIFIC_DIRECTORIES_TO_REMOVE:
            dir_path = self.project_root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Добавляем все файлы в директории
                for file_path in self._get_all_files_in_directory(dir_path):
                    rel_path = file_path.relative_to(self.project_root)
                    additional_junk.append(FileInfo(
                        path=str(rel_path),
                        size=file_path.stat().st_size if file_path.exists() else 0,
                        is_junk=True,
                        junk_reason=f"Файл в удаляемой директории: {dir_name}"
                    ))
        
        # 2. Временные .db файлы в корне
        for db_file in self.TEMP_DB_FILES:
            db_path = self.project_root / db_file
            if db_path.exists() and db_path.is_file():
                additional_junk.append(FileInfo(
                    path=db_file,
                    size=db_path.stat().st_size,
                    is_junk=True,
                    junk_reason="Временная база данных в корне проекта"
                ))
        
        # 3. Дублирующиеся .env файлы
        for env_file in self.DUPLICATE_ENV_FILES:
            env_path = self.project_root / env_file
            if env_path.exists() and env_path.is_file():
                additional_junk.append(FileInfo(
                    path=env_file,
                    size=env_path.stat().st_size,
                    is_junk=True,
                    junk_reason="Дублирующийся .env файл"
                ))
        
        # 4. __pycache__ директории
        for pycache_dir in self.project_root.rglob("__pycache__"):
            if pycache_dir.is_dir():
                for file_path in self._get_all_files_in_directory(pycache_dir):
                    rel_path = file_path.relative_to(self.project_root)
                    additional_junk.append(FileInfo(
                        path=str(rel_path),
                        size=file_path.stat().st_size if file_path.exists() else 0,
                        is_junk=True,
                        junk_reason="Кэш файл Python"
                    ))
        
        # 5. Файлы в instance/ (кроме основной БД)
        instance_dir = self.project_root / "instance"
        if instance_dir.exists():
            for file_path in instance_dir.iterdir():
                if file_path.is_file() and file_path.suffix in ['.db', '.db-shm', '.db-wal']:
                    rel_path = file_path.relative_to(self.project_root)
                    additional_junk.append(FileInfo(
                        path=str(rel_path),
                        size=file_path.stat().st_size,
                        is_junk=True,
                        junk_reason="Временные файлы базы данных"
                    ))
        
        return additional_junk
    
    def _cleanup_final_reports(self):
        """
        Специальная очистка папки final_reports - оставляем только последний отчет
        """
        final_reports_dir = self.project_root / self.FINAL_REPORTS_DIR
        
        if not final_reports_dir.exists() or not final_reports_dir.is_dir():
            return
        
        try:
            # Получаем все файлы отчетов
            report_files = []
            for file_path in final_reports_dir.iterdir():
                if file_path.is_file():
                    report_files.append(file_path)
            
            if len(report_files) <= 1:
                return  # Нечего удалять
            
            # Сортируем по времени модификации (последний - самый новый)
            report_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Удаляем все кроме последнего
            for file_path in report_files[1:]:
                try:
                    file_path.unlink()
                    self.logger.info(f"Удален старый отчет: {file_path.name}")
                except Exception as e:
                    self.logger.warning(f"Не удалось удалить отчет {file_path.name}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Ошибка при очистке final_reports: {e}")
    
    def _get_all_files_in_directory(self, directory: Path) -> List[Path]:
        """
        Получение всех файлов в директории рекурсивно
        
        Args:
            directory: Директория для обхода
            
        Returns:
            List[Path]: Список всех файлов
        """
        files = []
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    files.append(item)
        except Exception as e:
            self.logger.warning(f"Ошибка при обходе директории {directory}: {e}")
        
        return files
    
    def _create_optimization_summary(self, scan_result: ScanResult, cleanup_result: CleanupResult) -> Dict[str, any]:
        """
        Создание сводки по оптимизации
        
        Args:
            scan_result: Результат сканирования
            cleanup_result: Результат очистки
            
        Returns:
            Dict: Сводная информация
        """
        return {
            'total_files_scanned': scan_result.total_files,
            'total_project_size_before': scan_result.total_size,
            'junk_files_identified': len(scan_result.junk_files),
            'files_deleted': len(cleanup_result.deleted_files),
            'directories_deleted': len(cleanup_result.directories_deleted),
            'space_freed_bytes': cleanup_result.space_freed,
            'space_freed_mb': round(cleanup_result.space_freed / (1024 * 1024), 2),
            'backup_created': cleanup_result.backup_info is not None,
            'backup_path': cleanup_result.backup_info.backup_path if cleanup_result.backup_info else None,
            'errors_count': len(cleanup_result.errors),
            'warnings_count': len(cleanup_result.warnings),
            'operation_successful': cleanup_result.success,
            'duplicates_found': len(scan_result.duplicates),
            'large_files_found': len(scan_result.large_files),
            'empty_directories_found': len(scan_result.empty_directories)
        }
    
    def _generate_recommendations(self, scan_result: ScanResult, cleanup_result: CleanupResult) -> List[str]:
        """
        Генерация рекомендаций по дальнейшей оптимизации
        
        Args:
            scan_result: Результат сканирования
            cleanup_result: Результат очистки
            
        Returns:
            List[str]: Список рекомендаций
        """
        recommendations = []
        
        # Рекомендации по дубликатам
        if scan_result.duplicates:
            recommendations.append(
                f"Найдено {len(scan_result.duplicates)} групп дублирующихся файлов. "
                "Рассмотрите возможность удаления дубликатов."
            )
        
        # Рекомендации по большим файлам
        if scan_result.large_files:
            large_files_size = sum(f.size for f in scan_result.large_files)
            recommendations.append(
                f"Найдено {len(scan_result.large_files)} больших файлов "
                f"({round(large_files_size / (1024 * 1024), 2)} MB). "
                "Проверьте необходимость их хранения в репозитории."
            )
        
        # Рекомендации по .gitignore
        gitignore_path = self.project_root / '.gitignore'
        if gitignore_path.exists():
            recommendations.append(
                "Обновите .gitignore для предотвращения попадания временных файлов в репозиторий."
            )
        
        # Рекомендации по структуре проекта
        if cleanup_result.space_freed > 10 * 1024 * 1024:  # Больше 10MB
            recommendations.append(
                "Значительное количество мусорных файлов было удалено. "
                "Рассмотрите настройку автоматической очистки."
            )
        
        # Рекомендации по ошибкам
        if cleanup_result.errors:
            recommendations.append(
                f"Обнаружено {len(cleanup_result.errors)} ошибок при очистке. "
                "Проверьте права доступа к файлам и директориям."
            )
        
        # Рекомендации по бэкапу
        if cleanup_result.backup_info:
            recommendations.append(
                f"Создан бэкап в {cleanup_result.backup_info.backup_path}. "
                "Убедитесь что все работает корректно перед удалением бэкапа."
            )
        
        return recommendations
    
    def get_cleanup_statistics(self) -> Dict[str, any]:
        """
        Получение статистики по очистке проекта
        
        Returns:
            Dict: Статистика очистки
        """
        operations_history = self.cleaner.get_operations_history()
        
        total_operations = len(operations_history)
        successful_operations = sum(1 for op in operations_history if op.completed and not op.errors)
        total_files_deleted = sum(len(op.files_to_delete) for op in operations_history if op.completed)
        
        return {
            'total_cleanup_operations': total_operations,
            'successful_operations': successful_operations,
            'failed_operations': total_operations - successful_operations,
            'total_files_deleted': total_files_deleted,
            'backups_created': sum(1 for op in operations_history if op.backup_created),
            'last_cleanup': operations_history[-1].timestamp if operations_history else None
        }
    
    def validate_project_structure(self) -> Dict[str, any]:
        """
        Валидация структуры проекта после очистки
        
        Returns:
            Dict: Результат валидации
        """
        validation_result = {
            'critical_files_present': True,
            'missing_critical_files': [],
            'unexpected_junk_files': [],
            'structure_valid': True,
            'warnings': []
        }
        
        # Проверка критически важных файлов
        critical_files = [
            'requirements.txt',
            'config.py', 
            'run.py',
            'app/__init__.py',
            '.gitignore',
            'README.md'
        ]
        
        for critical_file in critical_files:
            file_path = self.project_root / critical_file
            if not file_path.exists():
                validation_result['missing_critical_files'].append(critical_file)
                validation_result['critical_files_present'] = False
        
        # Проверка на оставшиеся мусорные файлы
        scan_result = self.scanner.scan_project()
        if scan_result.junk_files:
            validation_result['unexpected_junk_files'] = [f.path for f in scan_result.junk_files]
            validation_result['warnings'].append(
                f"Найдено {len(scan_result.junk_files)} мусорных файлов после очистки"
            )
        
        # Проверка специфичных директорий
        for dir_name in self.SPECIFIC_DIRECTORIES_TO_REMOVE:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                validation_result['warnings'].append(f"Директория {dir_name} все еще существует")
        
        # Общая валидация структуры
        validation_result['structure_valid'] = (
            validation_result['critical_files_present'] and 
            not validation_result['unexpected_junk_files']
        )
        
        return validation_result