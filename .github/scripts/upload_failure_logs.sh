#!/usr/bin/env bash

set -e

cd $HOME

ARCHIVE_NAME=fail_log_${OS_NAME}_${COMPILE_CONFIG}.tar.gz
tar -czf ${ARCHIVE_NAME} $HOME/BUILD_* $HOME/SOURCE $HOME/LOGS $HOME/TOOLCHAINS

echo "Uploading archive $ARCHIVE_NAME"

scp -c aes128-ctr -P 30022 -p -i ${SSH_KEY} \
  -o PasswordAuthentication=no \
  -o StrictHostKeyChecking=no \
  $ARCHIVE_NAME \
  ci@tmp.kiwix.org:/data/tmp/ci
