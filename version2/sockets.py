#!/bin/bash

# Configuration
LOG_LEVEL="INFO"  # Can be DEBUG, INFO, WARNING, ERROR
JSON_OUTPUT=false

# Validate LOG_LEVEL setting
validate_log_level() {
    local valid_levels=("DEBUG" "INFO" "WARNING" "ERROR")
    if [[ ! " ${valid_levels[@]} " =~ " ${LOG_LEVEL} " ]]; then
        echo "Warning: Invalid LOG_LEVEL: $LOG_LEVEL. Using default: INFO" >&2
        LOG_LEVEL="INFO"
    fi
}

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
        if [[ "$level" == "ERROR" ]]; then
            echo "${timestamp} - ${level} - ${message}" >&2
        else
            echo "${timestamp} - ${level} - ${message}"
        fi
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
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  --json         Output socket summary in JSON format
  --log-level LEVEL Set log level (DEBUG, INFO, WARNING, ERROR)
  --help         Display this help message

Examples:
  $0 --json
  $0 --log-level DEBUG
  $0 --json --log-level WARNING
EOF
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
    
    # Extract comprehensive fields from /proc/net/sockstat
    parsed_data["SocketsUsed"]=$(echo "$output" | grep -E "^sockets:" | awk '{print $3}' || echo "N/A")
    
    # TCP fields
    parsed_data["TCPInUse"]=$(echo "$output" | grep -E "^TCP:" | awk '{print $3}' || echo "N/A")
    parsed_data["TCPOrphan"]=$(echo "$output" | grep -E "^TCP:" | awk '{print $5}' || echo "N/A")
    parsed_data["TCPTimeWait"]=$(echo "$output" | grep -E "^TCP:" | awk '{print $7}' || echo "N/A")
    parsed_data["TCPAlloc"]=$(echo "$output" | grep -E "^TCP:" | awk '{print $9}' || echo "N/A")
    parsed_data["TCPMemory"]=$(echo "$output" | grep -E "^TCP:" | awk '{print $11}' || echo "N/A")
    
    # UDP fields
    parsed_data["UDPInUse"]=$(echo "$output" | grep -E "^UDP:" | awk '{print $3}' || echo "N/A")
    parsed_data["UDPMemory"]=$(echo "$output" | grep -E "^UDP:" | awk '{print $5}' || echo "N/A")
    
    # UDPLITE fields (if available)
    parsed_data["UDPLITEInUse"]=$(echo "$output" | grep -E "^UDPLITE:" | awk '{print $3}' || echo "N/A")
    
    # RAW fields (if available)
    parsed_data["RAWInUse"]=$(echo "$output" | grep -E "^RAW:" | awk '{print $3}' || echo "N/A")
    
    # FRAG fields (if available)
    parsed_data["FRAGInUse"]=$(echo "$output" | grep -E "^FRAG:" | awk '{print $3}' || echo "N/A")
    parsed_data["FRAGMemory"]=$(echo "$output" | grep -E "^FRAG:" | awk '{print $5}' || echo "N/A")
    
    # Use jq for JSON formatting if available
    if command -v jq &> /dev/null; then
        printf '%s' "${parsed_data[@]}" | jq -n \
            --arg sockets "${parsed_data["SocketsUsed"]}" \
            --arg tcp_inuse "${parsed_data["TCPInUse"]}" \
            --arg tcp_orphan "${parsed_data["TCPOrphan"]}" \
            --arg tcp_tw "${parsed_data["TCPTimeWait"]}" \
            --arg tcp_alloc "${parsed_data["TCPAlloc"]}" \
            --arg tcp_mem "${parsed_data["TCPMemory"]}" \
            --arg udp_inuse "${parsed_data["UDPInUse"]}" \
            --arg udp_mem "${parsed_data["UDPMemory"]}" \
            --arg udplite "${parsed_data["UDPLITEInUse"]}" \
            --arg raw "${parsed_data["RAWInUse"]}" \
            --arg frag_inuse "${parsed_data["FRAGInUse"]}" \
            --arg frag_mem "${parsed_data["FRAGMemory"]}" \
            '{
                SocketsUsed: $sockets,
                TCP: {
                    inuse: $tcp_inuse,
                    orphan: $tcp_orphan,
                    time_wait: $tcp_tw,
                    allocated: $tcp_alloc,
                    memory: $tcp_mem
                },
                UDP: {
                    inuse: $udp_inuse,
                    memory: $udp_mem
                },
                UDPLITE: {
                    inuse: $udplite
                },
                RAW: {
                    inuse: $raw
                },
                FRAG: {
                    inuse: $frag_inuse,
                    memory: $frag_mem
                }
            }'
    else
        # Fallback to manual JSON formatting with proper escaping
        cat << EOF
{
    "SocketsUsed": "${parsed_data["SocketsUsed"]//\"/\\\"}",
    "TCP": {
        "inuse": "${parsed_data["TCPInUse"]//\"/\\\"}",
        "orphan": "${parsed_data["TCPOrphan"]//\"/\\\"}",
        "time_wait": "${parsed_data["TCPTimeWait"]//\"/\\\"}",
        "allocated": "${parsed_data["TCPAlloc"]//\"/\\\"}",
        "memory": "${parsed_data["TCPMemory"]//\"/\\\"}"
    },
    "UDP": {
        "inuse": "${parsed_data["UDPInUse"]//\"/\\\"}",
        "memory": "${parsed_data["UDPMemory"]//\"/\\\"}"
    },
    "UDPLITE": {
        "inuse": "${parsed_data["UDPLITEInUse"]//\"/\\\"}"
    },
    "RAW": {
        "inuse": "${parsed_data["RAWInUse"]//\"/\\\"}"
    },
    "FRAG": {
        "inuse": "${parsed_data["FRAGInUse"]//\"/\\\"}",
        "memory": "${parsed_data["FRAGMemory"]//\"/\\\"}"
    }
}
EOF
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
        --log-level)
            if [[ -n "$2" && "$2" != --* ]]; then
                LOG_LEVEL="$2"
                shift 2
            else
                log "ERROR" "Missing value for --log-level"
                exit 1
            fi
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

# Validate configuration
validate_log_level

# Main execution
check_sockstat_file
print_socket_summary
