# TODO: Merchant product upload fix

## Step 1
- Inspect `app/api/routes/merchant/products.py` for accidental FastAPI decorators on helper functions.

## Step 2
- Remove the `@router.post(..., response_model=ProductResponse)` decorators above `_parse_int_form`.

## Step 3
- Add a log line at the start of `create_product` to confirm whether the request enters the endpoint:
  - `logger.info("Entered create_product")`

## Step 4
- Deploy backend and confirm logs include `Entered create_product` after the frontend POST.

## Step 5
- If still no entry log, check browser DevTools:
  - request is actually hitting backend (status code 0/502/504 indicates network/proxy issues)
  - request content-type is `multipart/form-data`

