import urllib.request
url = "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2IzYmIyODIzMTdkNjQ5OGVhMzMzNjg2ZjBmMzRjMjUxEgsSBxCg5O6ckhsYAZIBJAoKcHJvamVjdF9pZBIWQhQxMDY2ODg1ODE2ODE0NTI5MzY0Mw&filename=&opi=96797242"
req = urllib.request.Request(url)
html = urllib.request.urlopen(req).read().decode('utf-8')
with open('stitch_index.html', 'w', encoding='utf-8') as f:
    f.write(html)
