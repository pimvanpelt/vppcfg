#!/bin/sh

## NOTE(pim):
## This integration test, while added to the public repository, is meant as an
## internal validation / regression / integration test suite to be run on Hippo
## and Rhino, two reference installs of VPP in IPng Networks. The config files
## here should not be used although they can be a source of config inspiration :)

## Run me:
# ./intest.sh 2>&1 | tee -a intest.out

  for i in hippo[0-9]*.yaml; do
    echo "Clearing: Moving to hippo-empty.yaml"
    ../vppcfg -s ../schema.yaml -c hippo-empty.yaml plan -o /tmp/vppcfg-exec-empty
    [ -s /tmp/vppcfg-exec-empty ] && vppctl exec /tmp/vppcfg-exec-empty
  
    for j in hippo[0-9]*.yaml; do
      echo " - Moving to $i .. "
      ../vppcfg -s ../schema.yaml -c $i plan -o /tmp/vppcfg-exec_$i
      [ -s /tmp/vppcfg-exec_$i ] && vppctl exec /tmp/vppcfg-exec_$i
  
      echo " - Moving from $i to $j"
      ../vppcfg -s ../schema.yaml -c $j plan -o /tmp/vppcfg-exec_${i}_${j}
      [ -s /tmp/vppcfg-exec_${i}_${j} ] && vppctl exec /tmp/vppcfg-exec_${i}_${j}
  
      echo " - Checking that from $j to $j is empty"
      ../vppcfg -s ../schema.yaml -c $j plan -o /tmp/vppcfg-exec_${j}_${j}_null
    done
  done
