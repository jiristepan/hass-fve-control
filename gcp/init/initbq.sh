gcloud config set project fve-control

# bq rm L0.update


bq mk \
 --table \
 --description "FVE updates" \
 --time_partitioning_type DAY \
 L0.update \
 ./update-schema.json

 bq mk \
 --table \
 --description "FVE decisions" \
 --time_partitioning_type DAY \
 L0.decisions \
 ./decisions-schema.json