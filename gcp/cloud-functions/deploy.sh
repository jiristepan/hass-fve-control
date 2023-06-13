gcloud functions deploy fve_decisions \
    --runtime python39 \
    --trigger-http \
    --allow-unauthenticated \
    --region europe-west1

gcloud functions deploy fve_update \
    --runtime python39 \
    --trigger-http \
    --allow-unauthenticated \
    --region europe-west1
