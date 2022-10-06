import os
import json
import base64

env = "dev"
secrets_dir = "SECRETS_ALL"
full_path = f'{env}/{secrets_dir}'
decoded_path = f'{env}/decoded'


class Secret:
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def get_name(self):
        return self.name

    def get_content(self):
        return self.content

    def get_decoded_content(self):
        decoded_secret = {}
        for key, value in self.get_content().items():
            decoded_secret[key] = base64.b64decode(value).decode("utf-8")
        return decoded_secret


def get_secret_file(path: str) -> list:
    try:
        os.listdir(os.path.abspath(path))  # todo it's wrong - should check if dir exsits and use only files
    except FileNotFoundError:
        print(f'Directory {path} does not exists')
        exit(1)
    else:
        return os.listdir(os.path.abspath(path))


def read_secrets_content_from_file(files: list):
    object_list = []
    for secret_file in files:
        try:
            os.path.abspath(full_path)
        except IsADirectoryError:  # todo
            print('There\'s a directory in folder')
        else:
            with open(f'{os.path.abspath(full_path)}/{secret_file}', 'r') as f:
                secret = Secret(secret_file, json.load(f))
                object_list.append(secret)
            f.close()

            return object_list


def save_decoded_secret_to_file(secrets_object_list: list):
    for secret in range(len(secrets_object_list)):
        with open(f'{os.path.abspath(decoded_path)}/{secrets_object_list[secret].get_name()}.json', 'w') as f:
            json.dump(secrets_object_list[secret].get_decoded_content(), f)
            f.close()


if __name__ == '__main__':
    get_secret_file(full_path)
    save_decoded_secret_to_file(read_secrets_content_from_file(get_secret_file(full_path)))
