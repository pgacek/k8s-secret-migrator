#!/bin/bash

for file in $(ls _*); do
  for secret in $(cat $file | jq -r); do
    APP=$(echo $file | awk -F '_' '{print $3}' | sed 's/.json//')

    echo mkdir -p ~/Desktop/secrets_extracted/${APP}
    mkdir -p ~/Desktop/secrets_extracted/${APP}

    #echo "kubectl get secret $secret -o jsonpath='{.data}' | jq >> ~/Desktop/secrets_extracted/${APP}/${secret}"
    #kubectl get secret $secret -o jsonpath='{.data}' | jq >> ~/Desktop/secrets_extracted/${APP}/${secret};

    echo "kubectl get secret $secret -o jsonpath='{.data}' | jq >> ~/Desktop/aws-secrets-manager/dev/SECRETS_ALL/${secret}"
    kubectl get secret $secret -o jsonpath='{.data}' | jq >> ~/Desktop/aws-secrets-manager/dev/SECRETS_ALL/${secret}
  done
done
