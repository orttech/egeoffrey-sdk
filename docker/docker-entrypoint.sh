#!/bin/sh

# welcome message
MANIFEST="manifest.yml"
SDK_MANIFEST="sdk/manifest.yml"
MYHOUSE_API_VERSION=$(echo -e "import sdk.python.constants\nprint sdk.python.constants.API_VERSION"|python)
echo -e "Package "$(yq -r .package $MANIFEST)" "$(yq -r .version $MANIFEST)"-"$(yq -r .revision $MANIFEST)" (SDK "$(yq -r .version $SDK_MANIFEST)"-"$(yq -r .revision $SDK_MANIFEST)" | API "$MYHOUSE_API_VERSION")"
echo -e "Environment settings: MODULES ["$MYHOUSE_MODULES"] | GATEWAY ["$MYHOUSE_GATEWAY_HOSTNAME" "$MYHOUSE_GATEWAY_PORT"] | HOUSE ["$MYHOUSE_ID"]"

# execute myHouse
if [ "$1" = 'myhouse' ]; then
    # run user setup script if found
    if [ -f "./docker/docker-init.sh" ]; then 
        echo -e "Running init script..."
        ./docker/docker-init.sh
    fi
    # start myHouse watchdog service
    echo -e "Starting watchdog..."
    exec python -m sdk.python.module.start
fi

# execute the provided command
exec "$@"