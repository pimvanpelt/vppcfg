#!/bin/sh

## NOTE(pim):
## This integration test, while added to the public repository, is meant as an
## internal validation / regression / integration test suite to be run on Hippo
## and Rhino, two reference installs of VPP in IPng Networks. The config files
## here should not be used although they can be a source of config inspiration :)

## Run me:
# ./intest.sh 2>&1 | tee intest.out


rm -f "intest.exec"

for i in hippo[0-9]*.yaml; do
  echo "Clearing: Moving to hippo-empty.yaml"
  ../vppcfg plan -s ../schema.yaml -c hippo-empty.yaml -o /tmp/vppcfg-exec-empty
  [ -s /tmp/vppcfg-exec-empty ] && {
	cat /tmp/vppcfg-exec-empty >> intest.exec
      vppctl exec /tmp/vppcfg-exec-empty
  }
  for j in hippo[0-9]*.yaml; do
    echo " - Moving to $i .. "
    ../vppcfg plan -s ../schema.yaml -c $i -o /tmp/vppcfg-exec_$i
    [ -s /tmp/vppcfg-exec_$i ] && {
	cat /tmp/vppcfg-exec_$i >> intest.exec
	vppctl exec /tmp/vppcfg-exec_$i
    }

    echo " - Moving from $i to $j"
    ../vppcfg plan -s ../schema.yaml -c $j -o /tmp/vppcfg-exec_${i}_${j}
    [ -s /tmp/vppcfg-exec_${i}_${j} ] && {
	cat /tmp/vppcfg-exec_${i}_${j} >> intest.exec
	vppctl exec /tmp/vppcfg-exec_${i}_${j}
    }

    echo " - Checking that from $j to $j is empty"
    ../vppcfg plan -s ../schema.yaml -c $j -o /tmp/vppcfg-exec_${j}_${j}_null
    [ -s /tmp/vppcfg-exec_${j}_${j}_null ] && {
      echo " - ERROR Transition is not empty"
      cat /tmp/vppcfg-exec_${j}_${j}_null
      exit 1
    }
  done
done
