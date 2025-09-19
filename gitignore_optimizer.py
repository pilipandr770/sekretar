#!/usr/bin/env python3
"""
GitignoreOptimizer - Анализ и оптимизация .gitignore файла для AI Secretary проекта
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass


@dataclass
class GitignoreAnalysis:
    """Результат анализа .gitignore файла"""
    existing_patterns: List[str]
    missing_patterns: List[str]
    ai_secretary_patterns: List[str]
    critical_files_status: Dict[str, bool]
    recommendations: List[str]


class GitignoreOptimizer:
    """Оптимизатор .gitignore файла для AI Secretary проекта"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.gitignore_path = self.project_root / ".gitignore"
        
        # AI Secretary специфичные паттерны
        self.ai_secretary_patterns = [
            # Базы данных
            "*.db",
            "*.db-shm", 
            "*.db-wal",
            "ai_secretary.db*",
            "dev.db*",
            "test*.db*",
            
            # Логи и отчеты
            "logs/",
            "*.log",
            "final_reports/",
            "test_execution_logs/",
            "test_execution_traces/",
            "validation_history.json",
            "validation_report.json",
            "cleanup.log",
            
            # Временные файлы и кэш
            "evidence/",
            "uploads/",
            "signal-cli/accounts/",
            "__pycache__/",
            ".pytest_cache/",
            
            # Конфигурационные файлы
            ".env*",
            "!.env.example",
            "!.env.example.new",
            "config/local.py",
            "instance/",
            
            # Бэкапы
            "*.backup_*",
            ".config_backup/",
            
            # Миграции (кроме __init__.py)
            "migrations/versions/*.py",
            "!migrations/versions/__init__.py",
            
            # Мониторинг и метрики
            "*.pid",
            "celerybeat-schedule*",
            
            # IDE и редакторы
            ".vscode/",
            ".idea/",
            "*.swp",
            "*.swo",
            "*~",
            
            # Системные файлы
            ".DS_Store*",
            "Thumbs.db",
            "ehthumbs.db",
            
            # Временные папки
            ".tmp/",
            ".temp/",
            "*.tmp",
            "*.temp"
        ]
        
        # Критически важные файлы, которые НЕ должны игнорироваться
        self.critical_files = [
            "requirements.txt",
            "config.py",
            "run.py",
            "app/__init__.py",
            "migrations/env.py",
            "migrations/alembic.ini",
            ".env.example",
            "README.md",
            "render.yaml",
            "docker-compose.yml",
            "Dockerfile"
        ]
    
    def read_current_gitignore(self) -> List[str]:
        """Читает текущий .gitignore файл"""
        if not self.gitignore_path.exists():
            return []
        
        with open(self.gitignore_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Убираем комментарии и пустые строки для анализа
        patterns = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
        
        return patterns
    
    def analyze_gitignore(self) -> GitignoreAnalysis:
        """Анализирует текущий .gitignore на полноту"""
        existing_patterns = self.read_current_gitignore()
        existing_set = set(existing_patterns)
        
        # Находим отсутствующие паттерны
        missing_patterns = []
        for pattern in self.ai_secretary_patterns:
            if pattern not in existing_set:
                # Проверяем похожие паттерны
                if not self._has_similar_pattern(pattern, existing_patterns):
                    missing_patterns.append(pattern)
        
        # Проверяем критически важные файлы
        critical_files_status = {}
        for file_path in self.critical_files:
            critical_files_status[file_path] = not self._would_be_ignored(file_path, existing_patterns)
        
        # Генерируем рекомендации
        recommendations = self._generate_recommendations(existing_patterns, missing_patterns, critical_files_status)
        
        return GitignoreAnalysis(
            existing_patterns=existing_patterns,
            missing_patterns=missing_patterns,
            ai_secretary_patterns=self.ai_secretary_patterns,
            critical_files_status=critical_files_status,
            recommendations=recommendations
        )
    
    def _has_similar_pattern(self, pattern: str, existing_patterns: List[str]) -> bool:
        """Проверяет есть ли похожий паттерн в существующих"""
        # Простая проверка для основных случаев
        if pattern == "*.db" and any("*.db" in p or "db.sqlite3" in p for p in existing_patterns):
            return True
        if pattern == "logs/" and any("*.log" in p for p in existing_patterns):
            return True
        if pattern == ".env*" and any(".env" in p for p in existing_patterns):
            return True
        return False
    
    def _would_be_ignored(self, file_path: str, patterns: List[str]) -> bool:
        """Проверяет будет ли файл игнорироваться"""
        # Упрощенная проверка - в реальности gitignore сложнее
        for pattern in patterns:
            if pattern.startswith('!'):
                continue
            if self._matches_pattern(file_path, pattern):
                return True
        return False
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Проверяет соответствует ли файл паттерну"""
        # Упрощенная реализация
        if pattern.endswith('/'):
            return file_path.startswith(pattern[:-1] + '/')
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '.*').replace('?', '.')
            return bool(re.match(regex_pattern, file_path))
        return file_path == pattern or file_path.endswith('/' + pattern)
    
    def _generate_recommendations(self, existing: List[str], missing: List[str], critical_status: Dict[str, bool]) -> List[str]:
        """Генерирует рекомендации по улучшению .gitignore"""
        recommendations = []
        
        if missing:
            recommendations.append(f"Добавить {len(missing)} отсутствующих паттернов для AI Secretary")
        
        ignored_critical = [f for f, status in critical_status.items() if not status]
        if ignored_critical:
            recommendations.append(f"ВНИМАНИЕ: {len(ignored_critical)} критически важных файлов могут игнорироваться")
        
        # Проверяем специфичные случаи
        if not any(".env" in p for p in existing):
            recommendations.append("Добавить игнорирование .env файлов")
        
        if not any("*.db" in p or "db.sqlite3" in p for p in existing):
            recommendations.append("Добавить игнорирование файлов баз данных")
        
        if not any("logs" in p for p in existing):
            recommendations.append("Добавить игнорирование папки logs/")
        
        return recommendations
    
    def create_optimized_gitignore(self) -> str:
        """Создает оптимизированный .gitignore"""
        # Читаем существующий файл полностью (с комментариями)
        existing_content = ""
        if self.gitignore_path.exists():
            with open(self.gitignore_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # Анализируем что нужно добавить
        analysis = self.analyze_gitignore()
        
        if not analysis.missing_patterns:
            return existing_content
        
        # Добавляем AI Secretary специфичные паттерны
        ai_secretary_section = "\n# AI Secretary specific patterns\n"
        for pattern in analysis.missing_patterns:
            ai_secretary_section += f"{pattern}\n"
        
        return existing_content + ai_secretary_section
    
    def optimize_gitignore(self) -> GitignoreAnalysis:
        """Оптимизирует .gitignore файл"""
        analysis = self.analyze_gitignore()
        
        if analysis.missing_patterns:
            optimized_content = self.create_optimized_gitignore()
            
            # Создаем бэкап
            backup_path = self.gitignore_path.with_suffix('.gitignore.backup')
            if self.gitignore_path.exists():
                import shutil
                shutil.copy2(self.gitignore_path, backup_path)
                print(f"Создан бэкап: {backup_path}")
            
            # Записываем оптимизированный файл
            with open(self.gitignore_path, 'w', encoding='utf-8') as f:
                f.write(optimized_content)
            
            print(f"Добавлено {len(analysis.missing_patterns)} новых паттернов в .gitignore")
        
        return analysis
    
    def validate_critical_files(self) -> Dict[str, bool]:
        """Валидирует что критически важные файлы не игнорируются"""
        patterns = self.read_current_gitignore()
        results = {}
        
        for file_path in self.critical_files:
            is_accessible = not self._would_be_ignored(file_path, patterns)
            results[file_path] = is_accessible
            
            if not is_accessible:
                print(f"ВНИМАНИЕ: Критически важный файл {file_path} может игнорироваться!")
        
        return results
    
    def print_analysis_report(self, analysis: GitignoreAnalysis):
        """Выводит отчет об анализе .gitignore"""
        print("=== АНАЛИЗ .GITIGNORE ===")
        print(f"Существующих паттернов: {len(analysis.existing_patterns)}")
        print(f"Отсутствующих паттернов: {len(analysis.missing_patterns)}")
        
        if analysis.missing_patterns:
            print("\nОтсутствующие паттерны:")
            for pattern in analysis.missing_patterns:
                print(f"  - {pattern}")
        
        print("\nСтатус критически важных файлов:")
        for file_path, is_accessible in analysis.critical_files_status.items():
            status = "✓ Доступен" if is_accessible else "✗ Может игнорироваться"
            print(f"  {file_path}: {status}")
        
        if analysis.recommendations:
            print("\nРекомендации:")
            for rec in analysis.recommendations:
                print(f"  - {rec}")


def main():
    """Основная функция для запуска оптимизации"""
    optimizer = GitignoreOptimizer()
    
    print("Анализ текущего .gitignore файла...")
    analysis = optimizer.analyze_gitignore()
    optimizer.print_analysis_report(analysis)
    
    if analysis.missing_patterns:
        print(f"\nОптимизация .gitignore...")
        optimizer.optimize_gitignore()
        print("Оптимизация завершена!")
    else:
        print("\n.gitignore файл уже оптимизирован!")
    
    # Финальная валидация
    print("\nВалидация критически важных файлов...")
    critical_status = optimizer.validate_critical_files()
    
    accessible_count = sum(1 for status in critical_status.values() if status)
    print(f"Доступно {accessible_count} из {len(critical_status)} критически важных файлов")


if __name__ == "__main__":
    main()