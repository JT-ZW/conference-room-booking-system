#!/usr/bin/env python3

import re

def check_duplicates():
    with open('routes/bookings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all route decorators
    routes = re.findall(r'@bookings_bp\.route\([^)]+\)', content, re.MULTILINE)
    route_counts = {}
    
    for route in routes:
        if route in route_counts:
            route_counts[route] += 1
        else:
            route_counts[route] = 1
    
    print("Route analysis:")
    duplicates_found = False
    for route, count in route_counts.items():
        if count > 1:
            print(f"DUPLICATE: {route} appears {count} times")
            duplicates_found = True
        else:
            print(f"OK: {route}")
    
    if not duplicates_found:
        print("\nNo duplicate routes found in decorators.")
    
    # Also check for function names
    functions = re.findall(r'def (\w+)\(', content)
    function_counts = {}
    
    for func in functions:
        if func in function_counts:
            function_counts[func] += 1
        else:
            function_counts[func] = 1
    
    print("\nFunction analysis:")
    for func, count in function_counts.items():
        if count > 1:
            print(f"DUPLICATE FUNCTION: {func} appears {count} times")

if __name__ == "__main__":
    check_duplicates()
