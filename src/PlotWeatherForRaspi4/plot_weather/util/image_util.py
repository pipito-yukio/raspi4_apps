""" 画像のフォーマット変換ユーティリティ """


def image_to_base64encoded(image_file):
    result = None
    with open(image_file, "rt", encoding=None) as fp:
        data = fp.read(-1)
        result = "data:image/png;base64," + data
    return result
