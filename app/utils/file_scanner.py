"""
File Scanner для анализа структуры проекта и идентификации мусорных файлов
"""
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import fnmatch


@dataclass
class FileInfo:
    """Информация о файле"""
    path: str
    size: int
    hash: Optional[str] = None
    is_junk: bool = False
    junk_reason: Optional[str] = None


@dataclass
class ScanResult:
    """Результат сканирования проекта"""
    total_files: int
    total_size: int
    junk_files: List[FileInfo]
    duplicates: Dict[str, List[str]]  # hash -> list of paths
    large_files: List[FileInfo]
    empty_directories: List[str]
    warnings: List[str]


class FileScanner:
    """Сканер файлов проекта для идентификации мусорных файлов"""
    
    # Паттерны мусорных файлов и папок
    JUNK_PATTERNS = [
        # Временные файлы Python
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '__pycache__',
        '*.egg-info',
        
        # Временные файлы тестов
        '.pytest_cache',
        '.coverage',
        'htmlcov',
        '.tox',
        
        # Временные файлы IDE
        '.vscode/settings.json',
        '.idea',
        '*.swp',
        '*.swo',
        '*~',
        
        # Логи и отчеты
        '*.log',
        'test_execution_logs',
        'test_execution_traces',
        'final_reports',
        
        # Временные базы данных
        '*.db-shm',
        '*.db-wal',
        'test*.db',
        'dev.db',
        'ai_secretary.db',  # в корне проекта
        
        # Демо и примеры
        'examples',
        'evidence',
        
        # Дублирующиеся env файлы
        '.env.local',
        '.env.development',
        '.env.production',
        '.env.test',
        
        # Другие временные файлы
        '*.tmp',
        '*.temp',
        '.DS_Store',
        'Thumbs.db',
    ]
    
    # Критически важные файлы, которые нельзя удалять
    CRITICAL_FILES = [
        'requirements.txt',
        'config.py',
        'run.py',
        'app/__init__.py',
        '.env.example',
        '.gitignore',
        'README.md',
        'render.yaml',
        'docker-compose.yml',
        'Dockerfile',
        'migrations',
        'app',
        '.git',
    ]
    
    # Размер файла для считания "большим" (в байтах)
    LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, project_root: str):
        """
        Инициализация сканера
        
        Args:
            project_root: Корневая папка проекта
        """
        self.project_root = Path(project_root).resolve()
        self.file_hashes: Dict[str, str] = {}
        
    def scan_project(self) -> ScanResult:
        """
        Сканирование всего проекта
        
        Returns:
            ScanResult: Результат сканирования
        """
        files: List[FileInfo] = []
        total_size = 0
        warnings = []
        
        try:
            for file_path in self._walk_directory(self.project_root):
                try:
                    file_info = self._analyze_file(file_path)
                    files.append(file_info)
                    total_size += file_info.size
                except (OSError, PermissionError) as e:
                    warnings.append(f"Не удалось проанализировать файл {file_path}: {e}")
                    
        except Exception as e:
            warnings.append(f"Ошибка при сканировании проекта: {e}")
        
        # Поиск дубликатов
        duplicates = self._find_duplicates(files)
        
        # Поиск больших файлов
        large_files = [f for f in files if f.size > self.LARGE_FILE_THRESHOLD]
        
        # Поиск пустых директорий
        empty_dirs = self._find_empty_directories()
        
        # Фильтрация мусорных файлов
        junk_files = [f for f in files if f.is_junk]
        
        return ScanResult(
            total_files=len(files),
            total_size=total_size,
            junk_files=junk_files,
            duplicates=duplicates,
            large_files=large_files,
            empty_directories=empty_dirs,
            warnings=warnings
        )
    
    def _walk_directory(self, directory: Path) -> List[Path]:
        """
        Рекурсивный обход директории
        
        Args:
            directory: Директория для обхода
            
        Returns:
            List[Path]: Список всех файлов
        """
        files = []
        
        try:
            for root, dirs, filenames in os.walk(directory):
                root_path = Path(root)
                
                # Пропускаем скрытые директории (кроме .git, .kiro)
                dirs[:] = [d for d in dirs if not d.startswith('.') or d in ['.git', '.kiro']]
                
                for filename in filenames:
                    file_path = root_path / filename
                    files.append(file_path)
                    
        except (OSError, PermissionError) as e:
            print(f"Ошибка при обходе директории {directory}: {e}")
            
        return files
    
    def _analyze_file(self, file_path: Path) -> FileInfo:
        """
        Анализ отдельного файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            FileInfo: Информация о файле
        """
        try:
            stat = file_path.stat()
            size = stat.st_size
            
            # Вычисление хеша для файлов меньше 1MB
            file_hash = None
            if size < 1024 * 1024:  # 1MB
                file_hash = self._calculate_hash(file_path)
                
            # Проверка на мусорный файл
            is_junk, junk_reason = self._is_junk_file(file_path)
            
            return FileInfo(
                path=str(file_path.relative_to(self.project_root)),
                size=size,
                hash=file_hash,
                is_junk=is_junk,
                junk_reason=junk_reason
            )
            
        except (OSError, PermissionError) as e:
            # Возвращаем базовую информацию для недоступных файлов
            return FileInfo(
                path=str(file_path.relative_to(self.project_root)),
                size=0,
                is_junk=False,
                junk_reason=f"Ошибка доступа: {e}"
            )
    
    def _calculate_hash(self, file_path: Path) -> str:
        """
        Вычисление MD5 хеша файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            str: MD5 хеш файла
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (OSError, PermissionError):
            return ""
    
    def _is_junk_file(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Проверка является ли файл мусорным
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Tuple[bool, Optional[str]]: (является_мусорным, причина)
        """
        relative_path = file_path.relative_to(self.project_root)
        path_str = str(relative_path)
        
        # Проверка критически важных файлов
        if self._is_critical_file(relative_path):
            return False, None
            
        # Проверка по паттернам
        for pattern in self.JUNK_PATTERNS:
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(file_path.name, pattern):
                return True, f"Соответствует паттерну: {pattern}"
                
            # Проверка папок в пути
            for part in relative_path.parts:
                if fnmatch.fnmatch(part, pattern):
                    return True, f"Находится в мусорной папке: {part}"
        
        # Специальные проверки
        
        # Временные .db файлы в корне
        if file_path.suffix == '.db' and len(relative_path.parts) == 1:
            if file_path.name not in ['ai_secretary.db']:  # основная БД может быть в корне
                return True, "Временная база данных в корне проекта"
        
        # Файлы в папке instance (кроме основной БД)
        if 'instance' in relative_path.parts and file_path.suffix in ['.db', '.db-shm', '.db-wal']:
            return True, "Временные файлы базы данных"
            
        # Дублирующиеся .env файлы
        if file_path.name.startswith('.env.') and file_path.name != '.env.example':
            return True, "Дублирующийся .env файл"
            
        return False, None
    
    def _is_critical_file(self, relative_path: Path) -> bool:
        """
        Проверка является ли файл критически важным
        
        Args:
            relative_path: Относительный путь к файлу
            
        Returns:
            bool: True если файл критически важен
        """
        path_str = str(relative_path)
        
        for critical in self.CRITICAL_FILES:
            if path_str.startswith(critical) or fnmatch.fnmatch(path_str, critical):
                return True
                
        return False
    
    def _find_duplicates(self, files: List[FileInfo]) -> Dict[str, List[str]]:
        """
        Поиск дублирующихся файлов по хешу
        
        Args:
            files: Список файлов
            
        Returns:
            Dict[str, List[str]]: Словарь хеш -> список путей
        """
        hash_to_files = defaultdict(list)
        
        for file_info in files:
            if file_info.hash and file_info.size > 0:  # Игнорируем пустые файлы
                hash_to_files[file_info.hash].append(file_info.path)
        
        # Возвращаем только дубликаты (больше одного файла с одинаковым хешем)
        return {h: paths for h, paths in hash_to_files.items() if len(paths) > 1}
    
    def _find_empty_directories(self) -> List[str]:
        """
        Поиск пустых директорий
        
        Returns:
            List[str]: Список пустых директорий
        """
        empty_dirs = []
        
        try:
            for root, dirs, files in os.walk(self.project_root):
                # Пропускаем .git и другие служебные папки
                if '.git' in root or '__pycache__' in root:
                    continue
                    
                if not dirs and not files:
                    relative_path = str(Path(root).relative_to(self.project_root))
                    empty_dirs.append(relative_path)
                    
        except (OSError, PermissionError) as e:
            print(f"Ошибка при поиске пустых директорий: {e}")
            
        return empty_dirs
    
    def get_junk_summary(self, scan_result: ScanResult) -> Dict[str, any]:
        """
        Получение сводки по мусорным файлам
        
        Args:
            scan_result: Результат сканирования
            
        Returns:
            Dict: Сводная информация
        """
        junk_size = sum(f.size for f in scan_result.junk_files)
        junk_by_reason = defaultdict(list)
        
        for file_info in scan_result.junk_files:
            junk_by_reason[file_info.junk_reason or "Неизвестная причина"].append(file_info.path)
        
        return {
            'total_junk_files': len(scan_result.junk_files),
            'total_junk_size': junk_size,
            'junk_size_mb': round(junk_size / (1024 * 1024), 2),
            'junk_by_reason': dict(junk_by_reason),
            'duplicates_count': len(scan_result.duplicates),
            'large_files_count': len(scan_result.large_files),
            'empty_directories_count': len(scan_result.empty_directories)
        }