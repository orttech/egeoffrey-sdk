#!/bin/sh

# welcome message
MYHOUSE_VERSION=$(echo -e "import sdk.constants\nprint sdk.constants.VERSION"|python)
MYHOUSE_API_VERSION=$(echo -e "import sdk.constants\nprint sdk.constants.API_VERSION"|python)
echo -e "\e[1;37;42mWelcome to myHouse v$MYHOUSE_VERSION (SDK v$MYHOUSE_SDK_VERSION, API $MYHOUSE_API_VERSION)\e[0m"

# user defined settings
echo -e "[\e[33mmyHouse\e[0m] Environment settings:"
echo "MODULES: $MYHOUSE_MODULES"
echo "GATEWAY: $MYHOUSE_GATEWAY_HOSTNAME $MYHOUSE_GATEWAY_PORT"
echo "HOUSE: $MYHOUSE_ID"

# execute myHouse
if [ "$1" = 'myhouse' ]; then
    # run user setup script if found
    if [ -f "./docker-init.sh" ]; then 
        echo -e "[\e[33mmyHouse\e[0m] Running init script..."
        ./docker-init.sh
    fi
    # start myHouse
    echo -e "[\e[33mmyHouse\e[0m] Starting module..."
    exec python -m sdk.module.start
fi

# execute the provided command
exec "$@"