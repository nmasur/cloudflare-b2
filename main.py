#!/usr/bin/env python

# From this article
# https://help.backblaze.com/hc/en-us/articles/360010017893-How-to-allow-Cloudflare-to-fetch-content-from-a-Backblaze-B2-private-bucket

import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

flagDebug = False

cloudflareEmail = os.environ["CLOUDFLARE_EMAIL"]
bucketSourceId = os.environ["BUCKET_SOURCE_ID"]
bucketFilenamePrefix = "notes/"
cfZoneId = os.environ["CLOUDFLARE_ZONE_ID"]
cfAppKey = os.environ["CLOUDFLARE_API_KEY"]
# the preceding 'b' causes these to be treated as binary data
# for b64 encoding.
b2AppKey = os.environ["B2_APP_KEY"].encode("ascii")
b2AppKeyId = os.environ["B2_APP_ID"].encode("ascii")

# An authorization token is valid for not more than 1 week
# This sets it to the maximum time value
maxSecondsAuthValid = 7*24*60*60 # one week in seconds

# DO NOT CHANGE ANYTHING BELOW THIS LINE ###

baseAuthorizationUrl = 'https://api.backblazeb2.com/b2api/v2/b2_authorize_account'
b2GetDownloadAuthApi = '/b2api/v2/b2_get_download_authorization'

cfUploadWWUrl = "https://api.cloudflare.com/client/v4/zones/" + cfZoneId + "/workers/script"

# Get fundamental authorization code

idAndKey = b2AppKeyId + b':' + b2AppKey
b2AuthKeyAndId = base64.b64encode(idAndKey)
basicAuthString = 'Basic ' + b2AuthKeyAndId.decode('UTF-8')
authorizationHeaders = {'Authorization' : basicAuthString}
resp = requests.get(baseAuthorizationUrl, headers=authorizationHeaders)

if flagDebug:
    print (resp.status_code)
    print (resp.headers)
    print (resp.content)

respData = json.loads(resp.content)

bAuToken = respData["authorizationToken"]
bFileDownloadUrl = respData["downloadUrl"]
bPartSize = respData["recommendedPartSize"]
bApiUrl = respData["apiUrl"]

# Get specific download authorization

getDownloadAuthorizationUrl = bApiUrl + b2GetDownloadAuthApi
downloadAuthorizationHeaders = { 'Authorization' : bAuToken}

resp2 = requests.post(getDownloadAuthorizationUrl,
                      json = {'bucketId' : bucketSourceId,
                              'fileNamePrefix' : bucketFilenamePrefix,
                              'validDurationInSeconds' : maxSecondsAuthValid },
                      headers=downloadAuthorizationHeaders )

resp2Data = json.loads(resp2.content)

bDownAuToken = resp2Data["authorizationToken"]

if flagDebug:
    print("authorizationToken: " + bDownAuToken)
    print("downloadUrl: " + bFileDownloadUrl)
    print("recommendedPartSize: " + str(bPartSize))
    print("apiUrl: " + bApiUrl)

workerTemplate = """addEventListener('fetch', event => {
    event.respondWith(handleRequest(event.request))
})
async function handleRequest(request) {
let authToken='<B2_DOWNLOAD_TOKEN>'
let b2Headers = new Headers(request.headers)
b2Headers.append("Authorization", authToken)
let urlpieces = request.url.split('/')
let hostname = urlpieces[2]
let path = urlpieces.slice(3, urlpieces.length).join("/")
let url = "https://" + hostname + "/file/noahmasur/notes/" + path
modRequest = new Request(url, {
    method: request.method,
    headers: b2Headers
})
const response = await fetch(modRequest)
return response
}"""

workerCode = workerTemplate.replace('<B2_DOWNLOAD_TOKEN>', bDownAuToken)


#Can now update the web worker
#curl -X PUT "https://api.cloudflare.com/client/v4/zones/:zone_id/workers/script" -H
#"X-Auth-Email:YOUR_CLOUDFLARE_EMAIL" -H "X-Auth-Key:ACCOUNT_AUTH_KEY" -H
#"Content-Type:application/javascript" --data-binary "@PATH_TO_YOUR_WORKER_SCRIPT"

cfHeaders = { 'X-Auth-Email' : cloudflareEmail,
              'X-Auth-Key' : cfAppKey,
              'Content-Type' : 'application/javascript' }

cfUrl = 'https://api.cloudflare.com/client/v4/zones/' + cfZoneId + "/workers/script"

resp = requests.put(cfUrl, headers=cfHeaders, data=workerCode)

if flagDebug:
    print(resp)
    print(resp.headers)
    print(resp.content)


