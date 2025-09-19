#!/usr/bin/env python3
"""
Скрипт для очистки и оптимизации проекта AI Secretary
"""
import sys
import logging
from pathlib import Path
import argparse
import json

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.cleanup_manager import CleanupManager


def setup_logging(verbose: bool = False):
    """Настройка логирования"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('cleanup.log')
        ]
    )


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Очистка и оптимизация проекта AI Secretary')
    parser.add_argument('--no-backup', action='store_true', 
                       help='Не создавать бэкап перед удалением')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Только анализ, без удаления файлов')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Подробный вывод')
    parser.add_argument('--backup-dir', type=str,
                       help='Папка для бэкапов')
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Инициализация менеджера очистки
        cleanup_manager = CleanupManager(
            project_root=str(project_root),
            backup_dir=args.backup_dir
        )
        
        logger.info("=== Начинаем очистку проекта AI Secretary ===")
        
        if args.analyze_only:
            # Только анализ
            logger.info("Режим анализа - файлы не будут удалены")
            scan_result = cleanup_manager.analyze_project()
            
            # Вывод результатов анализа
            summary = cleanup_manager.scanner.get_junk_summary(scan_result)
            
            print("\n=== РЕЗУЛЬТАТЫ АНАЛИЗА ===")
            print(f"Всего файлов в проекте: {scan_result.total_files}")
            print(f"Общий размер проекта: {round(scan_result.total_size / (1024 * 1024), 2)} MB")
            print(f"Мусорных файлов найдено: {summary['total_junk_files']}")
            print(f"Размер мусорных файлов: {summary['junk_size_mb']} MB")
            print(f"Дубликатов найдено: {summary['duplicates_count']} групп")
            print(f"Больших файлов: {summary['large_files_count']}")
            print(f"Пустых директорий: {summary['empty_directories_count']}")
            
            if scan_result.junk_files:
                print("\n=== МУСОРНЫЕ ФАЙЛЫ ===")
                for junk_file in scan_result.junk_files[:20]:  # Показываем первые 20
                    print(f"  {junk_file.path} ({junk_file.junk_reason})")
                
                if len(scan_result.junk_files) > 20:
                    print(f"  ... и еще {len(scan_result.junk_files) - 20} файлов")
            
            if scan_result.duplicates:
                print("\n=== ДУБЛИКАТЫ ===")
                for hash_val, paths in list(scan_result.duplicates.items())[:5]:
                    print(f"  Дубликаты:")
                    for path in paths:
                        print(f"    - {path}")
                    print()
            
        else:
            # Полная оптимизация
            create_backup = not args.no_backup
            logger.info(f"Режим оптимизации (бэкап: {'да' if create_backup else 'нет'})")
            
            result = cleanup_manager.optimize_project_structure(create_backup=create_backup)
            
            # Вывод результатов
            print("\n=== РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ ===")
            summary = result.optimization_summary
            
            print(f"Операция: {'УСПЕШНА' if result.cleanup_result.success else 'ЗАВЕРШЕНА С ОШИБКАМИ'}")
            print(f"Файлов удалено: {summary['files_deleted']}")
            print(f"Директорий удалено: {summary['directories_deleted']}")
            print(f"Освобождено места: {summary['space_freed_mb']} MB")
            
            if result.cleanup_result.backup_info:
                print(f"Бэкап создан: {result.cleanup_result.backup_info.backup_path}")
            
            if result.cleanup_result.errors:
                print(f"\nОШИБКИ ({len(result.cleanup_result.errors)}):")
                for error in result.cleanup_result.errors:
                    print(f"  - {error}")
            
            if result.cleanup_result.warnings:
                print(f"\nПРЕДУПРЕЖДЕНИЯ ({len(result.cleanup_result.warnings)}):")
                for warning in result.cleanup_result.warnings:
                    print(f"  - {warning}")
            
            if result.recommendations:
                print(f"\nРЕКОМЕНДАЦИИ:")
                for i, recommendation in enumerate(result.recommendations, 1):
                    print(f"  {i}. {recommendation}")
            
            # Валидация структуры проекта
            validation = cleanup_manager.validate_project_structure()
            print(f"\nВАЛИДАЦИЯ СТРУКТУРЫ: {'ПРОЙДЕНА' if validation['structure_valid'] else 'ПРОВАЛЕНА'}")
            
            if validation['missing_critical_files']:
                print("ВНИМАНИЕ: Отсутствуют критически важные файлы:")
                for file in validation['missing_critical_files']:
                    print(f"  - {file}")
            
            # Сохранение детального отчета
            report_path = project_root / 'cleanup_report.json'
            with open(report_path, 'w', encoding='utf-8') as f:
                report_data = {
                    'optimization_summary': summary,
                    'deleted_files': result.cleanup_result.deleted_files,
                    'deleted_directories': result.cleanup_result.deleted_directories,
                    'errors': result.cleanup_result.errors,
                    'warnings': result.cleanup_result.warnings,
                    'recommendations': result.recommendations,
                    'validation': validation
                }
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nДетальный отчет сохранен: {report_path}")
        
        logger.info("=== Очистка проекта завершена ===")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()