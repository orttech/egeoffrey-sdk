#!/bin/sh

# variables
SUPPORTED_MANIFEST_SCHEMA=2

# welcome message
MANIFEST="manifest.yml"
MANIFEST_SCHEMA=$(yq -r .manifest_schema $MANIFEST)
SDK_MANIFEST="sdk/manifest.yml"
API_VERSION=$(echo -e "import sdk.python.constants\nprint sdk.python.constants.API_VERSION"|python)

if [ $MANIFEST_SCHEMA != $SUPPORTED_MANIFEST_SCHEMA ]; then
    echo "ERROR: unsupported manifest schema v"$MANIFEST_SCHEMA
    exit
fi

echo -e "Package "$(yq -r .package $MANIFEST)" v"$(yq -r .version $MANIFEST |xargs printf '%.1f')"-"$(yq -r .revision $MANIFEST)" ("$(yq -r .branch $MANIFEST)") | SDK v"$(yq -r .version $SDK_MANIFEST |xargs printf '%.1f')"-"$(yq -r .revision $SDK_MANIFEST)" ("$(yq -r .branch $MANIFEST)") | API "$API_VERSION
echo -e "Environment settings: MODULES ["$EGEOFFREY_MODULES"] | GATEWAY ["$EGEOFFREY_GATEWAY_HOSTNAME" "$EGEOFFREY_GATEWAY_PORT"] | HOUSE ["$EGEOFFREY_ID"]"

# execute eGeoffrey
if [ "$1" = 'egeoffrey' ]; then
    # run user setup script if found
    if [ -f "./docker/docker-init.sh" ]; then 
        echo -e "Running init script..."
        ./docker/docker-init.sh
    fi
    # start eGeoffrey watchdog service
    echo -e "Starting watchdog..."
    exec python -m sdk.python.module.start
fi

# execute the provided command
exec "$@"