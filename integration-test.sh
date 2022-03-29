#!/bin/sh

for i in hippo[0-9]*.yaml; do
  echo "Clearing: Moving to hippo-empty.yaml"
  ./vppcfg -c hippo-empty.yaml > /tmp/vppcfg-exec-empty
  [ -s /tmp/vppcfg-exec-empty ] && vppctl exec /tmp/vppcfg-exec-empty

  for j in hippo[0-9]*.yaml; do
    echo " - Moving to $i .. "
    ./vppcfg -c $i > /tmp/vppcfg-exec_$i
    [ -s /tmp/vppcfg-exec_$i ] && vppctl exec /tmp/vppcfg-exec_$i

    echo " - Moving from $i to $j"
    ./vppcfg -c $j > /tmp/vppcfg-exec_${i}_${j}
    [ -s /tmp/vppcfg-exec_${i}_${j} ] && vppctl exec /tmp/vppcfg-exec_${i}_${j}

    echo " - Checking that from $j to $j is empty"
    ./vppcfg -c $j > /tmp/vppcfg-exec_${j}_${j}_null
  done

done
