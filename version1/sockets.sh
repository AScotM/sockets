#!/bin/bash

# Configuration
LOG_LEVEL="INFO"  # Can be DEBUG, INFO, WARNING, ERROR
JSON_OUTPUT=false

# Logging function with support for multiple log levels
log() {
    local level=$1
    local message=$2
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    local levels=("DEBUG" "INFO" "WARNING" "ERROR")
    local log_level_index=0
    local message_level_index=0
    
    # Find index of LOG_LEVEL and message level
    for i in "${!levels[@]}"; do
        [[ "${levels[$i]}" == "$LOG_LEVEL" ]] && log_level_index=$i
        [[ "${levels[$i]}" == "$level" ]] && message_level_index=$i
    done
    
    # Log only if message level is at or above LOG_LEVEL
    if [[ $message_level_index -ge $log_level_index ]]; then
        echo "${timestamp} - ${level} - ${message}"
    fi
}

# Check if /proc/net/sockstat file exists
check_sockstat_file() {
    if [[ ! -r /proc/net/sockstat ]]; then
        log "ERROR" "Error: '/proc/net/sockstat' not found or not readable. Ensure you are running on a Linux system with appropriate permissions."
        exit 1
    fi
}

# Display usage information
show_help() {
    echo "Usage: $0 [--json] [--help]"
    echo "Options:"
    echo "  --json     Output socket summary in JSON format"
    echo "  --help     Display this help message"
    exit 0
}

# Get socket summary from /proc/net/sockstat
get_socket_summary() {
    local start_time=$(date +%s.%N)
    log "INFO" "Reading socket statistics from /proc/net/sockstat..."
    
    # Read /proc/net/sockstat
    if ! output=$(cat /proc/net/sockstat 2>&1); then
        log "ERROR" "Failed to read /proc/net/sockstat: $output"
        return 1
    fi
    
    # Check for empty output
    if [[ -z "$output" ]]; then
        log "ERROR" "No data received from /proc/net/sockstat"
        return 1
    fi
    
    local end_time=$(date +%s.%N)
    local elapsed_time=$(echo "$end_time - $start_time" | bc -l | awk '{printf "%.4f", $0}')
    log "INFO" "Success! Retrieved socket summary in ${elapsed_time}s."
    
    if $JSON_OUTPUT; then
        parse_socket_summary "$output"
    else
        echo "$output"
    fi
}

# Parse socket summary to JSON
parse_socket_summary() {
    local output="$1"
    declare -A parsed_data
    
    # Extract specific fields from /proc/net/sockstat
    # Example /proc/net/sockstat content:
    # sockets: used 1234
    # TCP: inuse 567 orphan 0 tw 0 alloc 568 mem 10
    # UDP: inuse 89
    parsed_data["SocketsUsed"]=$(echo "$output" | grep -E "^sockets:" | awk '{print $3}' || echo "N/A")
    parsed_data["TCPInUse"]=$(echo "$output" | grep -E "^TCP:" | awk '{print $3}' || echo "N/A")
    parsed_data["UDPInUse"]=$(echo "$output" | grep -E "^UDP:" | awk '{print $3}' || echo "N/A")
    
    # Use jq for JSON formatting if available
    if command -v jq &> /dev/null; then
        echo "{}" | jq \
            --arg sockets "${parsed_data["SocketsUsed"]}" \
            --arg tcp "${parsed_data["TCPInUse"]}" \
            --arg udp "${parsed_data["UDPInUse"]}" \
            '{SocketsUsed: $sockets, TCPInUse: $tcp, UDPInUse: $udp}'
    else
        # Fallback to manual JSON formatting with proper escaping
        printf '{\n    "SocketsUsed": "%s",\n    "TCPInUse": "%s",\n    "UDPInUse": "%s"\n}\n' \
            "${parsed_data["SocketsUsed"]//\"/\\\"}" \
            "${parsed_data["TCPInUse"]//\"/\\\"}" \
            "${parsed_data["UDPInUse"]//\"/\\\"}"
    fi
}

# Main function
print_socket_summary() {
    log "INFO" "Welcome to the Socket Summary Analyzer"
    
    # Fetch and display socket summary
    local summary
    if ! summary=$(get_socket_summary); then
        log "ERROR" "Failed to retrieve socket summary"
        exit 1
    fi
    
    log "INFO" "Socket Summary:"
    echo "$summary"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            log "ERROR" "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
check_sockstat_file
print_socket_summary
