#!/usr/bin/env python3
"""
Простой тест системы очистки проекта
"""
import sys
import tempfile
import shutil
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.file_scanner import FileScanner
from app.utils.directory_cleaner import DirectoryCleaner
from app.utils.cleanup_manager import CleanupManager


def test_file_scanner():
    """Тест сканера файлов"""
    print("=== Тестирование FileScanner ===")
    
    scanner = FileScanner(str(project_root))
    scan_result = scanner.scan_project()
    
    print(f"✓ Всего файлов: {scan_result.total_files}")
    print(f"✓ Мусорных файлов: {len(scan_result.junk_files)}")
    print(f"✓ Дубликатов: {len(scan_result.duplicates)} групп")
    print(f"✓ Больших файлов: {len(scan_result.large_files)}")
    print(f"✓ Пустых директорий: {len(scan_result.empty_directories)}")
    
    # Проверяем что критические файлы не помечены как мусор
    critical_files = ['requirements.txt', 'config.py', 'run.py', 'README.md']
    junk_paths = [f.path for f in scan_result.junk_files]
    
    for critical_file in critical_files:
        if critical_file in junk_paths:
            print(f"✗ ОШИБКА: Критический файл {critical_file} помечен как мусор!")
            return False
        else:
            print(f"✓ Критический файл {critical_file} защищен")
    
    return True


def test_cleanup_manager():
    """Тест менеджера очистки"""
    print("\n=== Тестирование CleanupManager ===")
    
    # Создаем временную папку для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_backup_dir = Path(temp_dir) / "backups"
        
        cleanup_manager = CleanupManager(
            project_root=str(project_root),
            backup_dir=str(temp_backup_dir)
        )
        
        # Тест анализа
        scan_result = cleanup_manager.analyze_project()
        print(f"✓ Анализ проекта выполнен: {scan_result.total_files} файлов")
        
        # Тест получения статистики
        stats = cleanup_manager.get_cleanup_statistics()
        print(f"✓ Статистика получена: {stats['total_cleanup_operations']} операций")
        
        # Тест валидации структуры
        validation = cleanup_manager.validate_project_structure()
        print(f"✓ Валидация структуры: {'пройдена' if validation['structure_valid'] else 'провалена'}")
        
        if validation['missing_critical_files']:
            print(f"⚠ Отсутствуют критические файлы: {validation['missing_critical_files']}")
        
        return True


def test_patterns():
    """Тест паттернов для идентификации мусорных файлов"""
    print("\n=== Тестирование паттернов ===")
    
    scanner = FileScanner(str(project_root))
    
    # Тестовые случаи
    test_cases = [
        # (путь, должен_быть_мусором, ожидаемая_причина)
        ('.env.development', True, 'дублирующийся .env'),
        ('test.db', True, 'временная база данных'),
        ('__pycache__/test.pyc', True, 'кэш Python'),
        ('requirements.txt', False, 'критический файл'),
        ('app/__init__.py', False, 'критический файл'),
        ('examples/demo.py', True, 'демо файл'),
        ('final_reports/report.html', True, 'отчет'),
    ]
    
    for test_path, should_be_junk, expected_reason in test_cases:
        path = Path(test_path)
        is_junk, reason = scanner._is_junk_file(project_root / path)
        
        if is_junk == should_be_junk:
            print(f"✓ {test_path}: {'мусор' if is_junk else 'не мусор'}")
        else:
            print(f"✗ ОШИБКА: {test_path} должен быть {'мусором' if should_be_junk else 'не мусором'}")
            return False
    
    return True


def main():
    """Основная функция тестирования"""
    print("Запуск тестов системы очистки проекта...\n")
    
    tests = [
        test_file_scanner,
        test_cleanup_manager, 
        test_patterns
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_func.__name__} ПРОЙДЕН")
            else:
                print(f"✗ {test_func.__name__} ПРОВАЛЕН")
        except Exception as e:
            print(f"✗ {test_func.__name__} ОШИБКА: {e}")
    
    print(f"\n=== РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ===")
    print(f"Пройдено: {passed}/{total}")
    print(f"Статус: {'ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if passed == total else 'ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ'}")
    
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)