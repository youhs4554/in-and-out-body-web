#%%
import requests
import pandas as pd
import json
import os

url = "https://open.neis.go.kr/hub/schoolInfo"

service_key = os.environ['SCHOOL_API_KEY']

query = '대구외국어고등학교'

params = {
    'KEY' : service_key,
    'Type': 'json',
    'SCHUL_NM': query,
}

response = requests.get(url, params=params)

school_info = json.loads(response.text)['schoolInfo'][1]['row']
df = pd.DataFrame(school_info)[["SCHUL_NM", "ORG_TELNO", "ORG_RDNMA"]]
df.columns = ['학교명', '전화번호', '주소']
df
# %%
