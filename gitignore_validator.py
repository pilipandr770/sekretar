#!/usr/bin/env python3
"""
GitignoreValidator - Проверка корректности игнорирования файлов
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Результат валидации игнорируемых файлов"""
    properly_ignored: List[str]
    incorrectly_tracked: List[str]
    missing_files: List[str]
    validation_errors: List[str]
    recommendations: List[str]


class GitignoreValidator:
    """Валидатор корректности игнорирования файлов"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        
        # Файлы, которые ДОЛЖНЫ игнорироваться
        self.should_be_ignored = {
            # .env файлы
            ".env": "Основной файл окружения",
            ".env.local": "Локальные настройки",
            ".env.backup_20250918_205336": "Бэкап env файла",
            
            # Базы данных
            "ai_secretary.db": "Основная база данных",
            "dev.db": "База данных разработки", 
            "test.db": "Тестовая база данных",
            "test_auth.db": "База данных аутентификации",
            "instance/ai_secretary.db": "База данных в instance",
            "instance/ai_secretary.db-shm": "SQLite shared memory",
            "instance/ai_secretary.db-wal": "SQLite write-ahead log",
            "instance/test_integration.db": "Интеграционные тесты",
            "instance/test_seeder.db": "База данных сидера",
            
            # Логи
            "logs/database_errors_20250917.log": "Логи ошибок БД",
            "cleanup.log": "Логи очистки",
            
            # Отчеты и временные файлы
            "final_reports/": "Папка финальных отчетов",
            "test_execution_logs/": "Логи выполнения тестов",
            "test_execution_traces/": "Трейсы выполнения",
            "validation_history.json": "История валидации",
            "validation_report.json": "Отчет валидации",
            
            # Uploads и evidence
            "uploads/": "Папка загрузок",
            "evidence/": "Папка доказательств",
            
            # Конфигурационные бэкапы
            ".config_backup/": "Бэкапы конфигурации",
            
            # Signal CLI аккаунты
            "signal-cli/accounts/": "Аккаунты Signal CLI",
            
            # Кэш и временные файлы
            "__pycache__/": "Python кэш",
            ".pytest_cache/": "Pytest кэш",
            "*.pyc": "Скомпилированные Python файлы"
        }
        
        # Файлы, которые НЕ ДОЛЖНЫ игнорироваться
        self.should_not_be_ignored = {
            ".env.example": "Шаблон переменных окружения",
            ".env.example.new": "Новый шаблон переменных",
            "requirements.txt": "Зависимости Python",
            "config.py": "Основная конфигурация",
            "run.py": "Точка входа приложения",
            "README.md": "Документация проекта",
            "render.yaml": "Конфигурация Render",
            "docker-compose.yml": "Docker Compose конфигурация",
            "Dockerfile": "Docker образ",
            "migrations/env.py": "Конфигурация миграций",
            "migrations/alembic.ini": "Конфигурация Alembic",
            "app/__init__.py": "Инициализация приложения"
        }
    
    def check_git_status(self) -> Tuple[List[str], List[str]]:
        """Проверяет статус файлов в git"""
        try:
            # Получаем список отслеживаемых файлов
            result = subprocess.run(
                ["git", "ls-files"], 
                capture_output=True, 
                text=True, 
                cwd=self.project_root
            )
            tracked_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Получаем список неотслеживаемых файлов
            result = subprocess.run(
                ["git", "status", "--porcelain", "--ignored"], 
                capture_output=True, 
                text=True, 
                cwd=self.project_root
            )
            
            ignored_files = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('!!'):
                    ignored_files.append(line[3:])
            
            return tracked_files, ignored_files
            
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при выполнении git команды: {e}")
            return [], []
    
    def check_file_exists(self, file_path: str) -> bool:
        """Проверяет существование файла"""
        full_path = self.project_root / file_path
        return full_path.exists()
    
    def validate_env_files(self) -> ValidationResult:
        """Валидирует игнорирование .env файлов"""
        tracked_files, ignored_files = self.check_git_status()
        
        properly_ignored = []
        incorrectly_tracked = []
        missing_files = []
        validation_errors = []
        recommendations = []
        
        # Проверяем .env файлы
        env_files_to_ignore = [f for f in self.should_be_ignored.keys() if f.startswith('.env') and not f.endswith('.example')]
        
        for env_file in env_files_to_ignore:
            if self.check_file_exists(env_file):
                if env_file in tracked_files:
                    incorrectly_tracked.append(env_file)
                    validation_errors.append(f"КРИТИЧНО: {env_file} отслеживается git (может содержать секреты)")
                else:
                    properly_ignored.append(env_file)
            else:
                missing_files.append(env_file)
        
        # Проверяем что .env.example НЕ игнорируется
        for example_file in [f for f in self.should_not_be_ignored.keys() if 'example' in f]:
            if self.check_file_exists(example_file):
                if example_file not in tracked_files:
                    incorrectly_tracked.append(example_file)
                    validation_errors.append(f"ВНИМАНИЕ: {example_file} не отслеживается (должен быть в репозитории)")
                else:
                    properly_ignored.append(example_file)
        
        if incorrectly_tracked:
            recommendations.append("Убедитесь что .env файлы добавлены в .gitignore")
            recommendations.append("Удалите .env файлы из git: git rm --cached .env")
        
        return ValidationResult(
            properly_ignored=properly_ignored,
            incorrectly_tracked=incorrectly_tracked,
            missing_files=missing_files,
            validation_errors=validation_errors,
            recommendations=recommendations
        )
    
    def validate_database_files(self) -> ValidationResult:
        """Валидирует игнорирование файлов баз данных"""
        tracked_files, ignored_files = self.check_git_status()
        
        properly_ignored = []
        incorrectly_tracked = []
        missing_files = []
        validation_errors = []
        recommendations = []
        
        # Проверяем файлы баз данных
        db_files = [f for f in self.should_be_ignored.keys() if f.endswith('.db') or '.db-' in f]
        
        for db_file in db_files:
            if self.check_file_exists(db_file):
                if db_file in tracked_files:
                    incorrectly_tracked.append(db_file)
                    validation_errors.append(f"КРИТИЧНО: {db_file} отслеживается git (база данных не должна быть в репозитории)")
                else:
                    properly_ignored.append(db_file)
            else:
                missing_files.append(db_file)
        
        # Проверяем дополнительные паттерны БД
        for tracked_file in tracked_files:
            if (tracked_file.endswith('.db') or 
                '.db-shm' in tracked_file or 
                '.db-wal' in tracked_file):
                incorrectly_tracked.append(tracked_file)
                validation_errors.append(f"КРИТИЧНО: {tracked_file} - файл БД отслеживается git")
        
        if incorrectly_tracked:
            recommendations.append("Удалите файлы БД из git: git rm --cached *.db")
            recommendations.append("Убедитесь что *.db, *.db-shm, *.db-wal в .gitignore")
        
        return ValidationResult(
            properly_ignored=properly_ignored,
            incorrectly_tracked=incorrectly_tracked,
            missing_files=missing_files,
            validation_errors=validation_errors,
            recommendations=recommendations
        )
    
    def validate_logs_and_uploads(self) -> ValidationResult:
        """Валидирует игнорирование логов и uploads"""
        tracked_files, ignored_files = self.check_git_status()
        
        properly_ignored = []
        incorrectly_tracked = []
        missing_files = []
        validation_errors = []
        recommendations = []
        
        # Проверяем папки и файлы логов
        log_patterns = ['logs/', 'final_reports/', 'test_execution_logs/', 'test_execution_traces/', 'uploads/', 'evidence/']
        
        for pattern in log_patterns:
            if pattern.endswith('/'):
                # Проверяем папку
                folder_path = self.project_root / pattern[:-1]
                if folder_path.exists():
                    # Проверяем файлы в папке
                    for file_path in folder_path.rglob('*'):
                        if file_path.is_file():
                            relative_path = str(file_path.relative_to(self.project_root))
                            if relative_path in tracked_files:
                                incorrectly_tracked.append(relative_path)
                                validation_errors.append(f"ВНИМАНИЕ: {relative_path} в папке {pattern} отслеживается git")
                            else:
                                properly_ignored.append(relative_path)
            else:
                # Проверяем конкретный файл
                if self.check_file_exists(pattern):
                    if pattern in tracked_files:
                        incorrectly_tracked.append(pattern)
                        validation_errors.append(f"ВНИМАНИЕ: {pattern} отслеживается git")
                    else:
                        properly_ignored.append(pattern)
        
        # Проверяем логи по расширению
        for tracked_file in tracked_files:
            if (tracked_file.endswith('.log') and 
                not tracked_file.startswith('docs/') and 
                not tracked_file.startswith('scripts/')):
                incorrectly_tracked.append(tracked_file)
                validation_errors.append(f"ВНИМАНИЕ: {tracked_file} - лог файл отслеживается git")
        
        if incorrectly_tracked:
            recommendations.append("Убедитесь что logs/, uploads/, evidence/ в .gitignore")
            recommendations.append("Удалите лог файлы из git: git rm --cached logs/* uploads/* evidence/*")
        
        return ValidationResult(
            properly_ignored=properly_ignored,
            incorrectly_tracked=incorrectly_tracked,
            missing_files=missing_files,
            validation_errors=validation_errors,
            recommendations=recommendations
        )
    
    def validate_critical_files_not_ignored(self) -> ValidationResult:
        """Валидирует что критически важные файлы НЕ игнорируются"""
        tracked_files, ignored_files = self.check_git_status()
        
        properly_ignored = []  # В данном случае - правильно отслеживаемые
        incorrectly_tracked = []  # В данном случае - неправильно игнорируемые
        missing_files = []
        validation_errors = []
        recommendations = []
        
        for critical_file, description in self.should_not_be_ignored.items():
            if self.check_file_exists(critical_file):
                if critical_file in tracked_files:
                    properly_ignored.append(critical_file)  # Правильно отслеживается
                else:
                    incorrectly_tracked.append(critical_file)  # Неправильно игнорируется
                    validation_errors.append(f"КРИТИЧНО: {critical_file} ({description}) не отслеживается git")
            else:
                missing_files.append(critical_file)
                validation_errors.append(f"ОТСУТСТВУЕТ: {critical_file} ({description})")
        
        if incorrectly_tracked:
            recommendations.append("Добавьте критически важные файлы в git: git add <file>")
            recommendations.append("Проверьте .gitignore на исключения с ! для важных файлов")
        
        return ValidationResult(
            properly_ignored=properly_ignored,
            incorrectly_tracked=incorrectly_tracked,
            missing_files=missing_files,
            validation_errors=validation_errors,
            recommendations=recommendations
        )
    
    def run_comprehensive_validation(self) -> Dict[str, ValidationResult]:
        """Запускает комплексную валидацию"""
        results = {
            'env_files': self.validate_env_files(),
            'database_files': self.validate_database_files(),
            'logs_and_uploads': self.validate_logs_and_uploads(),
            'critical_files': self.validate_critical_files_not_ignored()
        }
        
        return results
    
    def print_validation_report(self, results: Dict[str, ValidationResult]):
        """Выводит отчет о валидации"""
        print("=== ОТЧЕТ ВАЛИДАЦИИ .GITIGNORE ===\n")
        
        total_errors = 0
        total_warnings = 0
        
        for category, result in results.items():
            category_names = {
                'env_files': 'ФАЙЛЫ ОКРУЖЕНИЯ (.env)',
                'database_files': 'ФАЙЛЫ БАЗ ДАННЫХ',
                'logs_and_uploads': 'ЛОГИ И ЗАГРУЗКИ',
                'critical_files': 'КРИТИЧЕСКИ ВАЖНЫЕ ФАЙЛЫ'
            }
            
            print(f"--- {category_names[category]} ---")
            print(f"Правильно обработано: {len(result.properly_ignored)}")
            print(f"Неправильно обработано: {len(result.incorrectly_tracked)}")
            print(f"Отсутствующих файлов: {len(result.missing_files)}")
            
            if result.validation_errors:
                print("Ошибки валидации:")
                for error in result.validation_errors:
                    print(f"  ❌ {error}")
                    if "КРИТИЧНО" in error:
                        total_errors += 1
                    else:
                        total_warnings += 1
            
            if result.recommendations:
                print("Рекомендации:")
                for rec in result.recommendations:
                    print(f"  💡 {rec}")
            
            print()
        
        # Общая сводка
        print("=== ОБЩАЯ СВОДКА ===")
        print(f"Критических ошибок: {total_errors}")
        print(f"Предупреждений: {total_warnings}")
        
        if total_errors == 0 and total_warnings == 0:
            print("✅ Все проверки пройдены успешно!")
        elif total_errors == 0:
            print("⚠️  Есть предупреждения, но критических ошибок нет")
        else:
            print("❌ Обнаружены критические ошибки, требуется исправление")


def main():
    """Основная функция для запуска валидации"""
    validator = GitignoreValidator()
    
    print("Запуск комплексной валидации .gitignore...")
    results = validator.run_comprehensive_validation()
    validator.print_validation_report(results)


if __name__ == "__main__":
    main()