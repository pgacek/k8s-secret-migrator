import base64
import logging
from pprint import pprint
from kubernetes import client, config

cluster_name = "k8s"
env = "dev"
namespace = "kitopi"
duplicated_secrets = ["kafka-bootstrap-servers", "dynatrace"]


class Secret:
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def get_name(self):
        return self.name

    def get_value(self):
        return self.content

    def get_decoded_content(self):
        decoded_secret = {}
        for key, value in self.get_value().items():
            decoded_secret[key] = base64.b64decode(value).decode("utf-8")
        return decoded_secret


def return_deployments_with_all_envs(all_deployments: kubernetes.client.models.v1_deployment_list.V1DeploymentList):
    """
    Return a dictionary with deployment name as key and list of envs as a values

    :param all_deployments:
    :return:
    """

    all_deployments_with_secrets_dict = {}
    for deployment_name in all_deployments.items:
        deployment_secrets_list = [it.to_dict() for it in deployment_name.spec.template.spec.containers[0].env]

        all_deployments_with_secrets_dict[deployment_name.metadata.name] = deployment_secrets_list

    return all_deployments_with_secrets_dict


def return_deployment_with_unique_secrets(deployments_dictionary):
    """
    This function returns the dictionary with key as a deployment name and value as a list of unique
    secrets

    :param deployments_dictionary:
    :return: dict
    """

    deployments_secrets_dict = {}
    for deployment_name, envs in deployments_dictionary.items():
        temp_list = set([
            env["value_from"]["secret_key_ref"]["name"]
            for env in envs if env["value_from"] is not None and env["value_from"]["secret_key_ref"] is not None
        ])
        deployments_secrets_dict[deployment_name] = list(temp_list)

    return deployments_secrets_dict


def remove_all_duplicates_and_return_filtered_deployment_dict(deployment_with_all_secrets):
    """
    This part of the code will find all the duplicates, removes them from the values in dict
    and put them in separate key "common"
    """

    all_secrets_list = []
    list_of_unique_secrets = set()
    list_of_duplicates = []

    for i in deployment_with_all_secrets.values():
        all_secrets_list += i

    for secret in all_secrets_list:
        if secret in list_of_unique_secrets:
            list_of_duplicates.append(secret)
        else:
            list_of_unique_secrets.add(secret)

    for key, value in deployment_with_all_secrets.items():
        for duplicate in set(list_of_duplicates):
            if duplicate in value:
                value.remove(duplicate)

    deployment_with_all_secrets["common"] = list_of_duplicates

    return deployment_with_all_secrets


def remove_selected_duplicates_from_list(deployment_with_all_secrets, list_of_duplicates):
    """
    At this moment we know that only duplicates we want to remove are "dynatrace" and "kafka-bootstrap-servers"

    :param deployment_with_all_secrets:
    :param list_of_duplicates:
    :return:
    """

    for key, value in deployment_with_all_secrets.items():
        for i in range(len(value)):
            for duplicate in list_of_duplicates:
                if duplicate in set(deployment_with_all_secrets[key]):
                    deployment_with_all_secrets[key].remove(duplicate)

    deployment_with_all_secrets["common"] = list_of_duplicates

    return deployment_with_all_secrets


def add_secrets_values_into_deployments_dictionary(all_deployments, secrets):
    """
    Put secrets values into a deployment dictionary

    :param all_deployments:
    :param secrets:
    :return:
    """

    temp_dict = {}
    for deployment_name in all_deployments:
        for secret_name in range(len(all_deployments[deployment_name])):

            temp_secret_name = all_deployments[deployment_name][secret_name]
            temp_key_name = all_deployments[deployment_name][secret_name]

            temp_dict[temp_key_name] = secrets[temp_secret_name]

            for item in temp_dict:
                if all_deployments[deployment_name][secret_name] == item:
                    all_deployments[deployment_name][secret_name] = {item: temp_dict[item]}

    return all_deployments


def return_k8s_secrets_with_values_as_dict(all_deployments):
    """
    This function reads secrets values from kubernetes namespace.
    Secrets are encoded in base64.
    Returns dictionary like below.

    { "secret_name1":
      {
        "key1": "value1",
        "key2": "value2"
      },
      "secret_name2":
      {
        "key3": "value3",
        "key4": "value4"
      }
    }

    :param all_deployments:
    :return:
    """
    secrets_values = {}
    for deployment_name in all_deployments:
        for secret_name in range(len(all_deployments[deployment_name])):
            k8s_secret_object = CoreV1.read_namespaced_secret(all_deployments[deployment_name][secret_name], namespace)
            secrets_values[k8s_secret_object.metadata.name] = k8s_secret_object.data

    return secrets_values


################################################


if __name__ == '__main__':


    config.load_kube_config()
    AppsV1 = client.AppsV1Api()
    CoreV1 = client.CoreV1Api()

    # get all deployments from k8s namespace and save in list
    k8s_deployments_list = AppsV1.list_namespaced_deployment(namespace)

    # create dictionary with deployment name as a key and all envs as a value
    k8s_deployments_with_envs = return_deployments_with_all_envs(k8s_deployments_list)

    # keep envs which are mounted from secrets
    k8s_deployments_with_mounted_envs_from_secrets = return_deployment_with_unique_secrets(k8s_deployments_with_envs)

    # remove selected secrets from deployment(duplicates) and put them into a "common" key
    k8s_deployments_with_secrets_no_values = remove_selected_duplicates_from_list(k8s_deployments_with_mounted_envs_from_secrets, duplicated_secrets)

    # read secrets from k8s and save them in dictionary
    k8s_secrets_with_values = return_k8s_secrets_with_values_as_dict(k8s_deployments_with_secrets_no_values)

    # add secrets values into a dictionary
    k8s_deployments_with_secrets_and_values = add_secrets_values_into_deployments_dictionary(k8s_deployments_with_secrets_no_values, k8s_secrets_with_values)

    # print whole structure
    pprint(k8s_deployments_with_secrets_and_values)
