import base64
from botocore.client import logger
from kubernetes import client, config
import boto3
import json
import botocore
import logging

logging.basicConfig(level=logging.INFO)

cluster_name = "k8s"
env = "dev"
namespace = "kitopi"
duplicated_secrets = ["kafka-bootstrap-servers", "dynatrace"]
create_secret = True


def return_deployments_with_all_envs(all_deployments: dict) -> dict:
    """
    Return a dictionary of deployments, with deployment name as a key and list of envs as a values

    :param all_deployments:
    :return:
    """

    all_deployments_with_secrets_dict = {}
    for deployment_name in all_deployments.items:
        deployment_secrets_list = [it.to_dict() for it in deployment_name.spec.template.spec.containers[0].env]

        all_deployments_with_secrets_dict[deployment_name.metadata.name] = deployment_secrets_list

    return all_deployments_with_secrets_dict


def return_deployment_with_unique_secrets(deployments_dictionary: dict) -> dict:
    """
    From deployment's dictionary, keep all envs which are mounted from secrets by ["value_from"]["secret_key_ref"]

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


def remove_selected_duplicates_from_list(deployment_with_envs: dict, list_of_duplicates: dict) -> dict:
    """
    Remove selected duplicates from deployment's secrets

    :param deployment_with_envs:
    :param list_of_duplicates:
    :return:
    """

    for key, value in deployment_with_envs.items():
        for i in range(len(value)):
            for duplicate in list_of_duplicates:
                if duplicate in set(deployment_with_envs[key]):
                    deployment_with_envs[key].remove(duplicate)

    deployment_with_envs["common"] = list_of_duplicates

    return deployment_with_envs


def add_secrets_values_into_deployments_dictionary(all_deployments: dict, secrets: dict) -> dict:
    """
    Add secrets values into deployment[secret]

    {"deployment_name1":
        ["secret_name1": {
          {
            "key1": "value1",
            "key2": "value2"
          },
        }
        "secret_name2":
          {
            "key1": "value3",
            "key2": "value4"
          }],
    "deployment_name2":
        ["secret_name3": {
          {
            "key1": "value5",
            "key2": "value6"
          },
        }]
    }

    :param all_deployments:
    :param secrets:
    :return:
    """

    deployments_with_secrets = {}
    for deployment_name in all_deployments:
        secrets_value_dict = {}
        for secret_name in all_deployments[deployment_name]:
            secrets_value_dict[secret_name] = secrets[secret_name]
        deployments_with_secrets[deployment_name] = [secrets_value_dict]

    return deployments_with_secrets


def decode_secrets(all_secrets: dict) -> dict:
    """
    Decode based64 secret's values

    :param all_secrets:
    :return:
    """
    for key, value in all_secrets.items():
        for secret_key in all_secrets[key]:
            value_to_decode = all_secrets[key][secret_key]
            all_secrets[key][secret_key] = base64.b64decode(value_to_decode).decode("utf-8")

    return all_secrets


def return_k8s_secrets_with_values_as_dict(all_deployments: dict) -> dict:
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


def create_or_update_secret_in_secret_manager(deployments_dict: dict, create_secret: bool) -> None:
    """
    Create or update existing secret object in AWS Secrets Manager

    :param deployments_dict:
    :param create_secret:
    :return:
    """
    secrets_failed_list = []

    for deployment_name, secrets_dict in deployments_dict.items():
        for secret in range(len(secrets_dict)):

            for secret_name, secret_value in secrets_dict[secret].items():
                aws_secret_name = f"/{cluster_name}-{env}/{namespace}/{deployment_name}/{secret_name}"

                if create_secret:
                    try:
                        r = c.create_secret(
                            Name=aws_secret_name,
                            SecretString=secret_value
                        )
                        logger.info(r)
                    except c.exceptions.ResourceExistsException as err:
                        secrets_failed_list.append(aws_secret_name)
                        logger.error(err.response["Error"]["Message"])
                        continue
                    except botocore.exceptions.ParamValidationError as err:
                        raise ValueError(logger.error(err))
                else:
                    try:
                        r = c.update_secret(
                            SecretId=aws_secret_name,
                            SecretString=json.dumps(secret_value)
                        )
                        logger.info(r)
                    except botocore.exceptions.ParamValidationError as err:
                        raise ValueError(logger.error(err))
                    except c.exceptions.ResourceNotFoundException as err:
                        secrets_failed_list.append(aws_secret_name)
                        logger.error(err.response["Error"]["Message"])
                        continue


################################################SecretsManager.Client.exceptions.ResourceNotFoundException



if __name__ == '__main__':
    c = boto3.client('secretsmanager')
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
    k8s_deployments_with_secrets_no_values = remove_selected_duplicates_from_list(
        k8s_deployments_with_mounted_envs_from_secrets, duplicated_secrets)

    k8s_secrets = decode_secrets(
        return_k8s_secrets_with_values_as_dict(k8s_deployments_with_secrets_no_values))

    k8s_secrets_encrypted = return_k8s_secrets_with_values_as_dict(k8s_deployments_with_secrets_no_values)

    deployments_with_secrets = add_secrets_values_into_deployments_dictionary(k8s_deployments_with_secrets_no_values,
                                                                              k8s_secrets)

    deployments_with_secrets_encrypted = add_secrets_values_into_deployments_dictionary(
        k8s_deployments_with_secrets_no_values, k8s_secrets_encrypted)


    create_or_update_secret_in_secret_manager(deployments_with_secrets, True)

