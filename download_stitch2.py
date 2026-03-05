import os
import urllib.request
import certifi
import ssl

ssl_context = ssl.create_default_context(cafile=certifi.where())

urls = [
    {
        "id": "20c2fe4851724efc99256756e7966deb",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVL8xln9NDu3LvluSz0ab6OWJNe7iz5TAqjuDI5KGLSLIhsOLkw3j5fx4u-QefNNEO-smEDJK3a4eyBgfOOCJ8aRJIjeT0JdaGmzzLqQLD9OKz8P-axV3xL3ZebwgsAqVtXhG2xvdquYx64uOmhdCmqYxCSE3DTV4xb1EFLWCVQG30yX9hReBL59vB8ORTTxR7hJKoIOn2SuU64-wRacGI9lyfsmxPHTbyxrm7n-nKwgRql1E5eTFlrLtL0",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzJlZjBmM2MwOTZkYTQ4ZmU4MDJjNzAwYmUxYzA0Y2UyEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "2433017d2a654ec18d374db44adea909",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVFqDKu4X_jzozvd3Dp9Gj26fn1tO-18fEUCgmdEu_WxYeNPFW6WLIz99jmLomp7EcK_LdBqliH-Ua4NaT1kbYVZqogJnvLK0rBWeFhMPfx-4c3aKAAWFiau0y3rT0CEDb1nnSaI9g3Cf9HPja5wjfgXrkXFZpA-PPe79eG-kmh90KQiw7C15Zqf_MavcKvGdkrML02FJkjCTuzExtiLKUMnESiPiw7QZ_ncxDf88MaE1yoNM7nFQPy8TLR",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzczMTYzNmE2ZmFiZTRiYjRhYzgxYjdiNzAzMWZmYzI2EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "374362d2d8c4440db6928dc1119e7415",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXSvheB0mudiZ_aAtGZl8CrdQRK-XjhqeVpc9mWc2W519-HZkWagzQj185oRePzYJ-q7cGxdNqnHvr8SIJa0BUS1gOaT5rw_E6T9wFaHEQh8Ot8htP6IxjoW5pAQZp6NqiDrRxApNAFoQ5QlPK_OUKkDg7--XlK2qjm-iLdNavnrY3_ifYl1yvMe71h8cFytIloVahG29XOwxocXA_kh7g_OSxFnJOsCmqmGBCmLWeybr6eQeuDcD9eyApf",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzk1NzZlYjM3MDFkODQ1MTM5MDdkZGJiYzUwODE4NDhiEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "c8aa629ecb804f3286e8e7f0813470cb",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWozJevztsan_YX1KyMMnZ47SNnGryrmYvNMXHT7a2yVKUMNAFw_8-BXkH5LKTYjJSIZPaaPojyuJ19FjI7c7gVIwreemkuR-4d_DekAS9dWJjj76ET9N_6PpXYiAYo3RTRL0ppYuS-W8-ueQnfQNGmzmEqYUpSECeh_PZQQy-k68e1FA0miKTZZ4eAtFsJ0pW6sID5XTPcO5so-jeoVIuGIbsPiGrrQMx7zvfVW0xU_Lb2QxM6e3wY43vQ",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzk0M2I0Yjk3OGE2NDQyYjA4ZDM0ODkyYjA1MmYyZWIxEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "cc6dfac0bd3449898039f65c9ee93645",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidU7TKzQ4MvKgNADTA2omsfcWMJYeOCn7PJWDRcXclSL5ud5yfcbq_DuV38fJca0Coc6kyvX8bq45i5X1-HskM76HvwnqvocBIvuuXd9tCIpGxS0sJcbhNY7gMTE3jody3fUH6dR1Ey4QG0_VcJ-bIVfz0U96mMmZu_Dfh3FS72O2Eti66zEjNNlHp3BiDfrBk60pSwjyPYcFZX8Cyc3cRRMlxygs0mtgCTXObHaGn3SwOsQX9p_V1K3cbHC",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzNjMTAyNGNkZWFjNjRhYTM5MDczN2QzMGRmNWMyZjg5EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "e281759baa1d4b769ee46b0c2b676155",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidX5sXil70LjFV1YibIaoUD5FYGsey9mlib6XsNpV1Bx71F4swmfDXCzaXAAhH8uieaQA7uJwIgeMB-kum73mNPnxBjX0sU4KvwirI8q230Gd1RQ_RtB1qvLjfYQ-r4eIaGxQqnd7XC7RisHDpFVm0S46B7V5bwbK3n67xscsrKbYP_sBIuQ1CugrYYBEqBlqbIQ4jflJvVqjbz9prfyoyB2MzL8Cw90mvNewE6QZeJqpm24_nkVfWlDsJ0",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzZlZGE1ZTQwMTY2YzQ4NGZhYjI2YjI5YmIzMWRlMGM5EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "ec73e248a9854d22a41d079d33ee377a",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidU0uqPRQi1hjwXOk8t6Js6Q9KbqandNCt3VGX1lv33qrqxAR5ddFP85_fAm9dCunxNznxsdBo6VwSq20qxEC3XO31v-0DIfTu_FGC23sQ3zVP3hrnIgR5X_3Tyc-jNzPQAOP7BFengMlrMXyzQTj6t2e2O93M1yiMoLTwCj_-K1pcgetxO5oItTxsRjQH17hz4jvhgw9VkCsArgu_RC51tDTQWsQySNXvfvoA0eXVb4Nk6e2UgRgmgPnQg",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2I4YzNkMGRmNGFkMDRjNzhiNDMwMTgxZGMxZDkzYjkxEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "f864922a0f814466ace95ddcf9f0ea7f",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWcpDQe__SosigPokIC--V6cfErt6aatsia6NyXf8TN6plLMGiak3AmSAWeJ5mCUKbfmF94APTqTxOKTcJYiSdBOFQt5zv_mt-S26D_4G3q4eAmjPNR1Tl62fjap-54eQTwLzAuwpEsxS_1zapuBN_Z1Ff2XWoy0qVaR91Pv87Rfdcx6Bk4K3YfSR_fAWJCb48Y4N5QbU7cV-KMOJ-I1q0MuykQZuSS3MteQfoeXXTWVSXPOYUCniTvc6wX",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2VhZDFiNDVhZmFjMTQzNzM4MTE3NjVhMGVhZDMxZWFlEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "e778dc21a054419f8b4d42809af44ff2",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXsKEQb37hMRbvz9P7gyzgef1tfGG6vS-VzzKvg7vDWhlSp8rgVNK8-YQzu2y4BKUvgj4JL3U67rh500xfUvFaVZLVwP-gx1V8EQZo4RqVh8QmwIfxq-ZmCCDL6xk3n6ZakcgJL67wqM10Ym39-ZG14b_HpG-0msfyJU6Id3uQ7bQSc0C99RhEn3DnTmwAdzgfE4RrlZWXG0AtM292B0TA3YT57v6K0ABkXtJZOBKyEIm8Rw6X684SZBjsK",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzQ2NmM0NmI4MmViYzQzZmFiNWQxNjQ5ZWVkOGZlNjVkEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "a812eb25ee3e45838acc50d990d01159",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXQnLSkmTSU36C_o_vkJJ_zJh5qTKJ1I7cmoDFOWTEL4GU0ltJ-MtmiuxYCM-YVEGSVKEZ2OFKjm7EVxxev2vK9Ks2HzCtGQy-evoSDbt11RfQaRqnf9kJlrcwW09XRYQvbKvpVGj22sp3_-wmiXM2k-XILcbsRTk49vRNY7uxoxLteYdX9ZzqG91coy_rodTagVUD9w0WLzjoTV8o1NCnUmSelQqEYVIhjXz5UqvfiXDZkrR2Pim5g0CY",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzA1Y2I1MWVjMmVmYjQ4NmY4ZWZlYTA5NDU3NzJjMzJmEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "36092fb08b874ca98f0e4ed27c9066fa",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVhZNZqK8ZfZnaENiqXbsG639UILasxoKF-dz6nnJIUr7RxpdMuOpcKbW-QP99Z07GOCUSR_OmBtU8YPjJfTAF3buMfXqkvz-_hzn_6uku8zI5V-LsR_IcmeZG0Mo0AyQgPyx6QA3XMWBLJ3gm5m2bSKwVZM2stXQkeg2iHDVy9QzQtb42YDCdcKnaYVErq-j1SnnT1bURtxOXj5rB8pHk0fCJujlIDMqCtAvaaC8gesGwjHikxq0pNmtxJ",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2E4NTEyNWU4YjE1YTQ4Y2RiYzcwOTFiMjlhNDIyNzMxEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "257393cdc38f49b1b274f8cd9bb335ce",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVSSDD4hCYCDrKAqT6VRpyMmHnPZ8qWeB1LLtVVE8wCa9BjC-5L94i4YLfFvd_ALxRmdXe_NhfuEx2h7c_VeWtNkHN9-xkSKwq4_94QpA7UZTBgSV4LMtxWRosIz6QdLUhUb2OO3_2eX3JCMrVWA_A8oSIY_lVMTv2KxXZHepTp5vpTOH077kE2hs5izhibKJ1ObpXxqdEBMI4r48uqjdkHW-Ut6c6J7-q_r-lrpden5arNLzWOH-VbpiFf",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2E0MzQ4NjdiOTk2ZDQ1MDFiZTlhYjY3MTI2Y2VkYjg0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "ef58465f591e47508da122c1cda2c903",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWC2Z3YX6oktAFia4VYBGuhuyLVKtZw161DNczdKIwCJek-0_JAiXl_mVKmb-bfTcid-4bfFXGxBKbR800HdyqFUjuG8xaT0yd8gCtLBDtNrPYd2HEuVtWy9nrkAiouJguHkixawxlLxCEbDwP6sXplfNMcvDK3Ffo1FGZanCodHKOjg2soAJHjfEQ1b0msakc_8gQd5oB0Kywq5WRl2RjC0-z7RfXcOT1hTdfbd-kqr3hCkOx5xUp1wiM",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzRmOTA1YTVjOGMyMzQ3NTdhMWUzYzU4N2U2ZDEwNDUyEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "76b6faf306eb4ab4895bbe7343b1af14",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidW3EbckD_VE4l3nghKlc0Ek_79I754WwTlHxMolDqQWQiVMrATCfgPjRnwOwLa3lEmql2SoQjkcwaCdSsdQ1Wahon4fQvRTM1BDoSKvaFfzoqDKL_ZC35MLhhhGbO7wB4VO4D4WT_jNbDTNNOQynWbPs2PQtrvELQr0Tw97UhWwFD6xlXe1p1H817_2ZBQXCF-x5wG6zv8UW63TDn2wbDK_hspooSJURUuibyNFGvg67Zz0QAthHKVLdMo",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2Y1OWUzYTZlOWM4YTQzMzM4ZTdkNGQyOGM4MzZlM2FiEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "8d9685e5f2d541efb8d35cf6a37bbf35",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWRVrl-S-uNaU1EdhBEgIleU22n7W9ZmNihuBFG5j0KhTxZ1987iKwgVdpENbWyhMWXwnLksXovLbtJX5ijGQJRjlOkUl5ZukN83bEeq9_cMH40wyBPn9_J8cnEV_zp6rquyuAPzjE2C4KpUP5X-wR-0Z0rgIYxNKOSGzhYMVJTLy9U6FXmf_5lpxjri9w__314zftEwnIJQiqHIufwVW-2Xeg3w1eTmdSm2m24dMYi5vkNz8CiU2Tp6HAq",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2M3ZjI5NWU5MDk0YjRiYjZhMTQwNDg1NzY3MDFhY2VjEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "0b013e3a4f56427e8fbc6cb10858c5c3",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidUBq-GRRH9k15jPTr9VGorVSOSo34ajcHZFqHy59vjGXkJoUZB0DWfamf8wIZuh77MDrkwJDEGEgMSbqVriyNFIWDX-idOomRih7jcFfCqMwMQCRH4ljkuCLRovdffY4fUCq2F0VAzo_-IhFtGL--CD04JLStJvUhJjnPiW0EDYRnGLcoi8abzzQIyte2gTXthk_9_ZV9YZPEErKzFb9A7ROlsDh4pa39AeggQNbcm2TcvY5Mx3wgQ0dSLH",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzVmOGJmMWMxNDY2ZTRkMDhhN2ExZDRhMWVhMjZlOGJjEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "34a25375164045209c9f58d893eae0ae",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWiHWozdCRzH8ZOwCGIbNC6sANZ3gW-i2PsOnT7HvOyM0ca2F9io6qdOii2sE6Rbpt3dnJ74ryTTaX_7AZiRtiueqZlUB5c_cB7oT5menXI6wD7jVinUkeqAloEoPmRfVsaujXcenUsse8nBOwoTeOTDjOiNI3S2lmHWZlmeKEXMKQ3xijZ1LwTpI9m2gY5gib8yasFeDhHrj_h4vGAWY1tL68Fcij3DEbFcMy7xyR3OhpWid4KjXDUzezO",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2I4M2I4YTc3ZDFlYTQxZjJiYzAzYmRmYjI2NmM2ZGI2EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "74c756010762411b9552864bda9da161",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidW-SpOLUePnENGuyXpLqEZ2b_k0VtGGz8j8lMlcYUAcDIL_yNzAdTctSbneNdIbKCNS1TH3CP3ZjKEucoPyR3zYEcR0G9o1pipXUm4vIXQZTQcjUb4vrCZUZo2gLTIBrrVip5yaK3uenXJgELRKWVL7vv0FNB3ke0mIS5I8PUCPmRCkohjx2D9N95oPhuGU55kl8eL1PJkJf5uHtiotZfHCFGo8rsu_O6QUYobuRD7lSvJcMVynxmW5-cw",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzQ0NzhmNjA1NzhlYTQwOTQ5NDFkZTFjZDZjYjJhYWJmEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "7a36d6443dcb4ece96b98aa75ab533ad",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXBOgv3LhzQ0rXph9KU_EDGFHYXpLEs40DdeGnpDQFW4NXbeurn8xgaM3r7sXEDlpB4VSIAqZPjvZHKHbbDXybG8FXOxJ4qMqudlLQyXuR5fAB0YdQTMho5dVqdtCzMZTeJG9Hyj607wqQgyf4s7PAZmbmw2KhTY5tatkCbOvIw2XyocUqCMNQFDGVOzarJxXegx7vu3IheXSnk6lfO0ACcXBRJvaEnkEzmNxcX3FVQd2Pa4QdgiN8Kl1LE",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2E1YjMwNzY3Y2M5NDQ5Y2ZhMjFiMmI5N2JkYWU4ZjI0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "a1a4a5cd3dcf4adc8d5deb51ec4c3d23",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVIBYJo6v1NDKb6KEQFsHpFb33QRYHoGejP83jOGdDI1SSy7sgwyTvDNeFTqEQeWJZL-CZkSkaV0-O6Aqeg0Wuuj9r6jxvYEtIQ-iXC7E0FpTnmh9aaOL0AVoY5oH-jW6oGbSn1fkQROY3lH3HgbnXKRjMVuD4naHJr2sq8SHMmjPPuvPp-QzNJFzmqA1Vp584KcEB1BRob6AnRuXYayTYGlpRrGl7Xj73UHMRNub591TboUnSsnzZLd3Y",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzdjZmYxZGQ3NTRjZDQxMGRhMmNiM2U4OGYzMzZmZGY0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "bb341657a02c469799766bf410449cbb",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWME-i_YxcCzF7lSzCS0DWQLZaBEF7NB_qt6UykFcXHIvX5kZRo1G1WAD-jUnw4uSEki3L2BQoHYLCt-o0R4e5D1GE1o_uakd0XgEEpUauZlTWOR1j9ZW3QeKrx9nov0TlDxoJQewRldp1IvmSq2Cw0VYzLREAvJrYHGEFKJ3Mj9LTuf5rC1I6DD-jgkf4nQGkBpQfEH2jnql75pbZVs3KJSDB9FtF60LAalncafNs2A8wMrn6vrZq5LjuU",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzJjZDcwNzI1MmY4YzQzMzFiMjE5ZjE1NGJiZGQzN2VjEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "c8eb3dd036f34322936b07a84608b2f8",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidULYUK1cD_8by_KstATHsoFkZjw0LhN51lyGyqKv_l_hWeplh-4Tj98hx0jkK8bZ1buo9Pg_pUTmj0lEzV5cj1Tps_ImwW2mgrZQ5Xy4JFWNeERUPISJWzVOlI98iiHPREarojBl7ubCV7OmK1rgyYXXWMgFSVFhFBfk2hzmjy34yK8xDxTo1Ux-qPUSwdiqCZYKvDo0u1L3Oldvm1RY7Gv4DKPwcQ5TeaNGkbUTlPWid49ocHykhm9CG5l",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2E0MWE2OTQ1NTU0YjRhMTY5Y2JjMWZjNGY2Njc1Yzg4EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "cb0d103957fb42edad4f0c78259fbe2f",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXVN-CGYqO5jBTQ6J9f6X2N041nodheiYAHQmhiTgld6fUDU1J3nbm_ByUfcOUNdUXFtA1DU5WKucv8eU1dKPGoNrrin-xn4DVxYF-akdABAhk2_kLAcqwATpO4xfuLPWuW_Wo3TnZQPgjF2sstIOoO6UejQi79lKNO8K05NiRFSN2FWo8yCJbphIsk3SUp3rf0ehkH2I-kd19V2EklrzCikmi-ir2vP9XB4I1c5O9VuZlLdXS7OsbjKzJG",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2ZiNTkyNTM0OGM5YzQwNWQ5OGVhZTUxOWU4OTYxNmQxEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
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
