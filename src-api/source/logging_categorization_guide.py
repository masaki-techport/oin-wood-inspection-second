#!/usr/bin/env python3
"""
Logging Categorization Guide for Wood Inspection Project

This script helps identify and categorize logging statements according to the new standards:

DEBUG: Development logs (sensor status, init routes, internal state changes)
INFO: User-relevant information (startup/shutdown, camera capture start, analysis start, image save)
WARNING: Non-critical warnings that don't prevent program continuation
ERROR: Critical failures that prevent program continuation
EXCEPTION: Exception handling and stack traces

Usage:
    python logging_categorization_guide.py [file_path]
"""

import os
import re
import sys
from pathlib import Path

def analyze_logging_patterns(file_path):
    """Analyze logging patterns in a file and suggest categorizations."""
    
    debug_patterns = [
        r'logger\.debug\(',
        r'logger\.info\(.*import.*\)',  # Import statements
        r'logger\.info\(.*initializ.*\)',  # Initialization details
        r'logger\.info\(.*load.*\)',  # Loading operations
        r'logger\.info\(.*config.*\)',  # Configuration details
        r'logger\.info\(.*threshold.*\)',  # Threshold updates
        r'logger\.info\(.*parameter.*\)',  # Parameter updates
        r'logger\.info\(.*buffer.*\)',  # Buffer operations
        r'logger\.info\(.*status.*\)',  # Internal status
    ]
    
    info_patterns = [
        r'logger\.info\(.*start.*\)',  # Startup operations
        r'logger\.info\(.*stop.*\)',  # Shutdown operations
        r'logger\.info\(.*capture.*\)',  # Camera capture
        r'logger\.info\(.*analy.*\)',  # Analysis operations
        r'logger\.info\(.*save.*\)',  # Save operations
        r'logger\.info\(.*process.*\)',  # Processing operations
        r'logger\.info\(.*complete.*\)',  # Completion messages
        r'logger\.info\(.*success.*\)',  # Success messages
    ]
    
    warning_patterns = [
        r'logger\.warning\(',
        r'logger\.warn\(',
    ]
    
    error_patterns = [
        r'logger\.error\(',
    ]
    
    exception_patterns = [
        r'logger\.exception\(',
    ]
    
    suggestions = {
        'debug': [],
        'info': [],
        'warning': [],
        'error': [],
        'exception': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Check for debug patterns
            for pattern in debug_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    suggestions['debug'].append(f"Line {line_num}: {line}")
                    break
            
            # Check for info patterns
            for pattern in info_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    suggestions['info'].append(f"Line {line_num}: {line}")
                    break
            
            # Check for warning patterns
            for pattern in warning_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    suggestions['warning'].append(f"Line {line_num}: {line}")
                    break
            
            # Check for error patterns
            for pattern in error_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    suggestions['error'].append(f"Line {line_num}: {line}")
                    break
            
            # Check for exception patterns
            for pattern in exception_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    suggestions['exception'].append(f"Line {line_num}: {line}")
                    break
                    
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return None
    
    return suggestions

def print_analysis(file_path, suggestions):
    """Print analysis results."""
    print(f"\n{'='*80}")
    print(f"LOGGING ANALYSIS: {file_path}")
    print(f"{'='*80}")
    
    for level, items in suggestions.items():
        if items:
            print(f"\n{level.upper()} LEVEL ({len(items)} items):")
            print("-" * 40)
            for item in items:
                print(f"  {item}")
    
    print(f"\n{'='*80}")

def main():
    """Main function."""
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            suggestions = analyze_logging_patterns(file_path)
            if suggestions:
                print_analysis(file_path, suggestions)
        else:
            print(f"File not found: {file_path}")
    else:
        print("Usage: python logging_categorization_guide.py [file_path]")
        print("\nThis script analyzes logging patterns and suggests categorizations.")
        print("Run it on individual files to get detailed analysis.")

if __name__ == "__main__":
    main()
