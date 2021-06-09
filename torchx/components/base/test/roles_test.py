#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.


import os
import unittest
from dataclasses import asdict

from torchx.components.base.roles import create_torch_dist_role
from torchx.specs.api import Resource, Role, macros


class TorchDistRoleBuilderTest(unittest.TestCase):
    def test_build_create_torch_dist_role(self) -> None:
        # runs: python -m torch.distributed.launch
        #                    --nnodes 2:4
        #                    --max_restarts 3
        #                    --no_python True
        #                    --rdzv_backend etcd
        #                    --rdzv_id ${app_id}
        #                    /bin/echo hello world
        elastic_trainer = create_torch_dist_role(
            "elastic_trainer",
            image="test_image",
            entrypoint="/bin/echo",
            script_args=["hello", "world"],
            script_envs={"ENV_VAR_1": "FOOBAR"},
            port_map={"foo": 8080},
            nnodes="2:4",
            max_restarts=3,
            no_python=True,
        ).replicas(2)
        self.assertEqual("elastic_trainer", elastic_trainer.name)
        self.assertEqual("python", elastic_trainer.entrypoint)
        self.assertEqual(
            [
                "-m",
                "torch.distributed.launch",
                "--nnodes",
                "2:4",
                "--max_restarts",
                "3",
                "--no_python",
                "--rdzv_backend",
                "etcd",
                "--rdzv_id",
                macros.app_id,
                "--role",
                "elastic_trainer",
                "/bin/echo",
                "hello",
                "world",
            ],
            elastic_trainer.args,
        )
        self.assertEqual({"ENV_VAR_1": "FOOBAR"}, elastic_trainer.env)
        self.assertEqual(2, elastic_trainer.num_replicas)

    def test_build_create_torch_dist_role_override_rdzv_params(self) -> None:
        role = create_torch_dist_role(
            "test_role",
            image="torch_image",
            entrypoint="user_script.py",
            script_args=["--script_arg", "foo"],
            nnodes="2:4",
            rdzv_backend="etcd",
            rdzv_id="foobar",
        )
        self.assertEqual(
            [
                "-m",
                "torch.distributed.launch",
                "--nnodes",
                "2:4",
                "--rdzv_backend",
                "etcd",
                "--rdzv_id",
                "foobar",
                "--role",
                "test_role",
                os.path.join(macros.img_root, "user_script.py"),
                "--script_arg",
                "foo",
            ],
            role.args,
        )

    def test_build_create_torch_dist_role_flag_args(self) -> None:
        role = create_torch_dist_role(
            "test_role", "torch_image", "user_script.py", no_python=False
        )
        self.assertEqual(
            [
                "-m",
                "torch.distributed.launch",
                "--rdzv_backend",
                "etcd",
                "--rdzv_id",
                macros.app_id,
                "--role",
                "test_role",
                os.path.join(macros.img_root, "user_script.py"),
            ],
            role.args,
        )

    def test_build_create_torch_dist_role_img_root_already_in_entrypoint(
        self,
    ) -> None:
        role = create_torch_dist_role(
            "test_role",
            "torch_image",
            os.path.join(macros.img_root, "user_script.py"),
            no_python=False,
        )
        self.assertEqual(
            [
                "-m",
                "torch.distributed.launch",
                "--rdzv_backend",
                "etcd",
                "--rdzv_id",
                macros.app_id,
                "--role",
                "test_role",
                os.path.join(macros.img_root, "user_script.py"),
            ],
            role.args,
        )

    def test_json_serialization_factory(self) -> None:
        """
        Tests that an ElasticRole can be serialized into json (dict)
        then recreated as a Role. An ElasticRole is really just a builder
        utility to make it easy for users to create a Role with the entrypoint
        being ``torch.distributed.launch``
        """
        resource = Resource(cpu=1, gpu=0, memMB=512)
        role = create_torch_dist_role(
            "test_role",
            "user_image",
            "user_script.py",
            resource=resource,
            script_args=["--script_arg", "foo"],
            port_map={"tensorboard": 8080},
            nnodes="2:4",
            rdzv_backend="etcd",
            rdzv_id="foobar",
        ).replicas(3)

        # this is effectively JSON
        elastic_json = asdict(role)
        resource_json = elastic_json.pop("resource")
        elastic_json["resource"] = Resource(**resource_json)
        role = Role(**elastic_json)
        self.assertEqual(resource, role.resource)
        self.assertEqual(role.name, role.name)
        self.assertEqual(role.entrypoint, role.entrypoint)
        self.assertEqual(
            role.args,
            role.args,
        )
        self.assertEqual(asdict(role), asdict(role))
