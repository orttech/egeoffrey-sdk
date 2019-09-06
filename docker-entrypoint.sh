#!/bin/sh

# variables
SUPPORTED_MANIFEST_SCHEMA=2
PACKAGE_MANIFEST="manifest.yml"
SDK_MANIFEST="sdk/manifest.yml"
API_VERSION=$(echo -e "import sdk.python.constants\nprint sdk.python.constants.API_VERSION"|python)

# Get the package manifest schema version if the file exists
if [ -f "$PACKAGE_MANIFEST" ]; then
    MANIFEST_SCHEMA=$(yq -r .manifest_schema $PACKAGE_MANIFEST)
    if [ $MANIFEST_SCHEMA != $SUPPORTED_MANIFEST_SCHEMA ]; then
        echo "ERROR: unsupported manifest schema v"$MANIFEST_SCHEMA
        exit
    fi
fi

# welcome message (package)
if [ -f "$PACKAGE_MANIFEST" ]; then
    echo -e "Package "$(yq -r .package $PACKAGE_MANIFEST)" v"$(yq -r .version $PACKAGE_MANIFEST |xargs printf '%.1f')"-"$(yq -r .revision $PACKAGE_MANIFEST)" ("$(yq -r .branch $PACKAGE_MANIFEST)") | SDK v"$(yq -r .version $SDK_MANIFEST |xargs printf '%.1f')"-"$(yq -r .revision $SDK_MANIFEST)" ("$(yq -r .branch $SDK_MANIFEST)") | API "$API_VERSION
    echo -e "Environment settings: MODULES ["$EGEOFFREY_MODULES"] | GATEWAY ["$EGEOFFREY_GATEWAY_HOSTNAME" "$EGEOFFREY_GATEWAY_PORT"] | HOUSE ["$EGEOFFREY_ID"]"
# welcome message (sdk)
else
    echo -e "SDK v"$(yq -r .version $SDK_MANIFEST |xargs printf '%.1f')"-"$(yq -r .revision $SDK_MANIFEST)" ("$(yq -r .branch $SDK_MANIFEST)") | API "$API_VERSION
fi

# execute eGeoffrey
if [ "$1" = 'egeoffrey' ]; then
    # run user setup script if found
    if [ -f "./docker-init.sh" ]; then 
        echo -e "Running init script..."
        ./docker-init.sh
    fi
    # start eGeoffrey watchdog service
    echo -e "Starting watchdog..."
    exec python -m sdk.python.module.start
fi

# execute the provided command
exec "$@"