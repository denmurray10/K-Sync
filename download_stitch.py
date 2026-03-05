import os
import urllib.request
import certifi
import ssl

ssl_context = ssl.create_default_context(cafile=certifi.where())

urls = [
    {
        "id": "9a9fca8060e849d2863191db54738c29",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidUfbaLSp7kjM_rYsSjnv9RkJRv49nAlgaQeIje6zEumxI1N13Y1mHz6QdIIZd-Qkc8FgEQxvW8EPgInbbyQBsupM6lf3wtF3iFhZGJnT7O2Ve928aer2v-sa-NmhSPBBRZLt9xQizxXfFzHfJ9_kAXTxeqmqRuRaqm2Y0jw7DFpEWGt0gKTKDo4jat-t9K3ATrHGC6gMo_HicTrpW7h8BeHfhS5OfabDnRbNUmIg6e1WWREMCjVKSDQ2tI",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzBhMjcyNWJiYTJmZjRjMmFiZWYxNzg1ZmRlZGY3YmQzEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "3b8992a94e3c4b0faa95004f82553fc1",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXQfXD90-I9nhUHUtbzbZoiI7bvmiGEwpZ3W4Ndwpxl7ZUsQgUaznQsL-MAzGN6_5FZua7g-EznNo1VrBObME2kkcqsUlZEJFVlCkjG5fC2dXqHIsa4I63faD8t4facxdC4q9N7NB-hYZg7di4oxDKHZLJ_0ETOGQv9EX-RN4wlw6OdrZpEa554QZeaGinss73sew-plKghe_WIz9uJDMdtjelAv_VygbusOORJJVsjf6vu-MNpvcR-J_Bk",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzg4OGY2ZGU4YWIxOTRhZTNiMjNkMzEzMTllMjRlYmU0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "41642e86efde48908cc384c9459c44bb",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidU9luMWXxPSwx823D4kARK8XReZigzIgL3pA6i7Z9Ry8zTEgXRw-WSEUKmB-23Zr56KX6z5teXqtJVCiPRfkjXcEp4kM_lyAyWIL1Rntz5DVThlBq_sTCFGqPNMM-WQ8YzxtfHCvnoMw48E0K4REeA6WQOi8Tv42vxws1XwTAzAGPmrHRtWXYnMpbbBApGDMqNq0UnCQKYhXSVmeHz62FsJwXv9-ZLwXkk86r-5NitTeYlJiEKOwqq36sw",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzRlZTNiM2NlYzEyYjQ4YjE4NGJkMjUwMGYzZGFiMTkyEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "3640664e98904abaa20ae1b8ed537fa9",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidV6uycyrzTUtjPqURAcvXPdKb5Bj-5xmOtFpcZ4H4ge9jIBtY-hX-tvjDtxLQw4EsyVHt9NLmdPHVlLK8ohAtt7K0PFdyHyaMakF0d4UemM-Lq_oxp1WuPMc-nqVMc2VekTjSag8nnOpdmLD_fR5qB0ZnO9xM1jeA2xtk5zdIVkPo4SdzY5xi3QGFrK5PGsFqiVNl051Yf8Zum2tMfgoGTBGeezAo6X8-GbsH5zSlrry_K4wVV3dSlrjCUL",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzM3NmQyOTY1ZWEyYzRkZmY5ZjJlNDk5ZmY5NDIyMDFhEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "d8df07311f6f430a98fef959fbfef3cf",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVdfM32DS70qsFy6h29C4vqRi-3x-ITQz8D0doClGO3tTXprrBa0T4T5BdPbcAynJ9S3_gz96YFKjr62Kz5IowmuKuB5KB4qarYRS4yMzVPQ8-KtUeHgWdXcCo4xoJq870oxDJvhQ_yBzCHj5jF_EtPtwlZo1BgOE-7MR5EoCblPjNe6ndPPAJvdjJ3Whx1Ws7FKYQbNgXb1ceo7W9GndjU8vTku60XRU3txzXWHPahC5eOBhhbIZ2722M",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2NlMWU1NTQxZTc3OTQxNDI4NzYwYWE1ZDQ4YjljNTE2EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "1f45bcc86daf49ee96d2bec08b238ace",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVgF4GqfJlgiqCpVV6D17cFvJEcvtNirTH4zFWua84Gtf9f7zNZSIRQWWbsw_9QpQpbtEorFb4ahNdenHoXwRk8Zzg_PVRtZEXhjfHF455ut1_7NjW-PC1Q68KMDWXQiijWiOTFmrCWWFj-FobNP-BnWTy_k2rG0aAEEX1bay3b1v8C6ejS89RG-ArOI7t6J5Gucx2VClXfCJMLkOH3idKqAU07dsZ4mb3-JLg9RNm9pb-0yBaVKBCzEDfX",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzhmMDk1OWQ1OWQxMTRkODI4OTU5Y2Q5YTgxYzYzMjZkEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "1227a7ef915d40119df12a9c55df9c2a",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidV4Q4s5XjW9uDqV5jZCPeuP4BH5xHsnqMSI7Y09dRIMhIrTs-E4xKy3SPZ3zdYs7Yala80Hdlh2X_BoO2CiC8iEVu3mxRZVPxm-OMFv_NGtOWtqoNYocYPo73MY6DwYPOFgy6gP5aKZFU3ACnoTB6N5hcmfYdC5ReQJHIJTKTfOfQ-lMR1LiBurZBqnkyVMiyzRVj74POxzftVSeOX4NjiZIFrz8SH1B5bLgnSX7_2vqOgkprG8oKJ77AwX",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzdhMmJkOTBjZGVkOTRmMzM4ZTFmMWMxMjljNjA5YjAxEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "d9d4ed95efd94546938de0e058bb4c9c",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidUOb5kRA1RSDeDiKlKyhE5EKA6UdSO4MJVPLflngzbcGUG-1UW4jJTBhABLdQRtPJ1puzWixNO5WD-aXptptnr6BfnZfeXkVflRBNP7Wx15tyrjAmzMEcLx1i-0d9IfKKxheoYe_Wk5shDQVA2wDbc5D4Y5dOXi8chLJrsgqG1fGcUT97aK_KLXa2SNXYdzolQbrAor7g4qXxjkjQANT1hnQdKZNp1EbrAoxShrApblG0PoaqxVYHA55sw7",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2Q3NjliYzgxZDI0MjQ4NWE5YTQ3NDQ3MWFiMjQzMDBiEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "8f3ed7f6eee24a56a92fe81b32512f26",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidUBa8kLRJ0DwAa34jk64OF1pR2wTtwpMsDrbEq07eVv9Ag1DlPAwycTcl0JLj8YQRiVa10FAoFwRt1uGCTppqIPlBof9o3Uz149n5w-HBVELqHb_-T1E2uzMtXuZwhYCjveKlSpiwMsKDMz1y5YzBeRQtgmKKHMIC-3raxquyEt8UWW0lkxIV8wrFnTiaMtAymhHyQ8an4nE42aL8i2PEHeBrDszh00QS4xnQlbO2ZnT-1lNGCJu2ca6VPj",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzQwZjAyMTMxNjRkNjRlY2ViMjM4NzM2Y2VmZjkyZmZhEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "6ee9092bb3c64a10a1a9cac4b45bfdb1",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXwY3LrMuuBHpMOVPevPEJIayGxsxBtBdI_qK2E2-HU29Qmc7whNJgFGHVo2BLnARxd4uQQajaMt98hzBP_IRiqHHdc8nFiYaqThoG3JF7YNPRfAz_B3tHK8OSfE-4LdwUhcdLLQ4Z-omsKezBe0ExW53UI9712i23S8m7cNfujk5VBehO9k6rmB2dsUTjHhfQYH_i8XdwdPXXKKdyBJ5Gt67FSHi2Dp_9Pb4Ee4A6DHGxfJqMo4WQOtBNJ",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2FiZGM5ZDhjOWNkZTQxM2Y4NTE1ZTJkZWZhYTQwYWUwEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "8da5e4bde1ff4c47af5b49cad6f1d779",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVDK_eXNaDCT987EgiPkLr84fh0WdmcjFPcZOnfQce3rwBdmV9DVd7P9m6IMg4HbaKGQ5_yc-Dx2EkGQIWmPbb-VxXLKgELF-1oJdJuBGuvieI-OfCVPGC3huWsCI3y_lE6mVY8Ap2a409XtoXP6zxA89WffxUDVtdRbsy96bkhS5VFlUaM-yiZwHfh6-M4vxWfO_qah9yS-wvZMUE3pLWYRnPrYK568anvN3XT5US4Vdtt4sz1xM2blVmB",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzg4MjMzNjFiODczOTQyNjk5NDk3OGY2NDU1N2YwMDI2EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "cf42ae0a995a42f8a6988ddd63389436",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidV44x2o8pliVq6_iAPU2YR8b7tOqWs_aVSLLZeKigXNw56C7KomrwpVjCtGNmFxBUJwtcbh_hx8a4WvMan8g26FqnQaGcq4vCmNqFFmjfAsQLF54Mcdq24lWbACJTbSAKheaNKZMssYSSXXCXSgaNlgnVfP4e3mWxANCpVNtO_62gyuvI7mdpa0cQLXw2Jwtp-N_86lYSWZ6H8pKEfSIe6JBYxU75GiIQCVoJgt2lkg4bMxGT9B43XCXTA",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2ZlMDNiNDgwNDY2ZjRhMGI4YTBhMWM2MjZmYjMyZGI0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "547def5b35c341e2b53c4490cf1d984a",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidU8EDFGFWnrH-k4W3fSYX7OKic0otxnKEFYo6CsKtDnkxdwH7O5_0cmiDxCDEbjAkPth-e0iVMPENIdZpiHspzHCSDmDLYmpJIIhJRmO6dPbMhruDS-eIvXygQT8YomFnzg_p-K3x2ZXUpz6YCd5jsVXjRdP85ej-RFX7O7PMeCi3N07EPz3LCcSfVpivrHT_fbkDJfssz1EyP_yzfyuc3RmNazxPtV5RAb2PlbaRD5FOgDi8XYfoPeUqE",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzM1NDU4ZTIzNWMzNjQzZTlhMjQxNDA1YjAwOGE5OWVhEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "5ad1968019064e1ebc84ffefc802dd0c",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVhitaYVLgZW3cP7t0kC323h6I9UnYuFuBTWHIDblxD0gK0LqGreSfCki2hDOpPYPz7ez3s7BhedUxa69i_KM4HSJf9wmMvjBZKcTDIhRSQPy9X1yl7qeWgFeJyNPazZHgzBugCrc9cJbEAzGo9X6Za1UeGlCW-vgpWtkePLNGJrqUHngDQgZZtb7dajq-4cXwaDoRrXrUlURT8H1vsnNqk2ufw0mjKlC0KbcaNsLwwYFdZ_7bRhFr94Mav",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2JjNTE0NGQ3NzAyYzRiNWJiMDVhMTRlMzY1MWYwODhmEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "1d22c80e4f734a099a7aed1c390c5d79",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidUEUjnYW-LSIvCVVlj_YPvM7h_D6xA11xIjrwHAAC9VaRT-g1QHT3UpmVEBNFYBOXK4ftDMtfuSUeSO9ZDoTDBQMa-mikJBB-jXBjKXfzgK_ruBfQ9Rox7G0CQFbv9qGswl-gpsgtFMWuCgkbPQlDqhTrd57oYI_QSEBPJ9Bfm6WA61zVB9KfKuehtzPGDThydBSfKgcO0YLZLYc5qZr1Ag_h9fGlIe5FYvPb7eaTCEtiJ2n9PElVeq4AxX",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2Q1NGQ5YzJiOGRiNzRmMGE5N2FmMzgzMTRiMmQ5NWVkEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    }
]

import time

download_dir = "stitch_downloads"
os.makedirs(download_dir, exist_ok=True)

for item in urls:
    screen_id = item["id"]
    print(f"Downloading {screen_id}...")
    
    # Download HTML
    html_path = os.path.join(download_dir, f"{screen_id}.html")
    if not os.path.exists(html_path):
        req = urllib.request.Request(item["html"], headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, context=ssl_context) as response, open(html_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Failed HTML {screen_id}: {e}")
        time.sleep(2)

    # Download Screenshot
    screenshot_path = os.path.join(download_dir, f"{screen_id}.png")
    if not os.path.exists(screenshot_path):
        req = urllib.request.Request(item["screenshot"], headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, context=ssl_context) as response, open(screenshot_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Failed Screenshot {screen_id}: {e}")
        time.sleep(2)

print("Done")
