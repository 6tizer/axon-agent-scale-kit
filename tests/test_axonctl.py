import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))
import axonctl


class AxonCtlRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.network_file = self.base / "network.yaml"
        self.agents_file = self.base / "agents.yaml"
        self.state_file = self.base / "state.json"
        self.hosts_file = self.base / "hosts.yaml"
        self.network_file.write_text(
            yaml.safe_dump(
                {
                    "rpc_url": "https://mainnet-rpc.axonchain.ai/",
                    "evm_chain_id": 8210,
                    "cosmos_chain_id": "axon_8210-1",
                    "deploy": {"default_concurrency": 2, "retry_times": 1},
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        self.agents_file.write_text(
            yaml.safe_dump(
                {
                    "agents": [
                        {"name": "agent-001", "wallet_ref": "KEY_001"},
                        {"name": "agent-002", "wallet_ref": "KEY_002"},
                        {"name": "agent-003", "wallet_ref": "KEY_003"},
                    ]
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        self.hosts_file.write_text(
            yaml.safe_dump(
                {
                    "hosts": [
                        {
                            "name": "test-host",
                            "host": "10.0.0.1",
                            "user": "root",
                            "ssh_key": "/tmp/test.pem",
                            "workdir": "/opt/axon-agent-scale",
                            "python_bin": "python3",
                            "use_sudo": False,
                        }
                    ]
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        self.valid_address = "0x1111111111111111111111111111111111111111"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    def test_validate_passes_with_standard_network(self, _rpc_mock: mock.Mock) -> None:
        self.assertEqual(axonctl.validate(str(self.network_file), str(self.agents_file), strict_rpc=True), 0)

    def test_render_service_unit_contains_execstart(self) -> None:
        unit = axonctl.render_service_unit(
            service_name="axon-agent-agent-001.service",
            agent_name="agent-001",
            remote_workdir="/opt/axon-agent-scale",
            python_bin="python3",
        )
        self.assertIn("ExecStart=python3 /opt/axon-agent-scale/scripts/agent_worker.py --agent agent-001", unit)

    def test_funding_wallet_template_and_import(self) -> None:
        wallet_file = self.base / "funding_wallet.template.yaml"
        self.assertEqual(axonctl.funding_wallet_template(str(wallet_file)), 0)
        data = yaml.safe_load(wallet_file.read_text(encoding="utf-8"))
        data["address"] = self.valid_address
        data["private_key"] = "a" * 64
        wallet_file.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        self.assertEqual(axonctl.funding_wallet_import(str(self.state_file), str(wallet_file)), 0)
        state = axonctl.load_state(str(self.state_file))
        self.assertEqual(state["settings"]["funding_address"], self.valid_address)

    def test_request_create_rejects_insufficient_min_funding(self) -> None:
        code = axonctl.create_request(
            state_file=str(self.state_file),
            target_agents=2,
            min_funding_axon=150.0,
            funding_address=self.valid_address,
            min_confirmations=2,
            timeout_sec=600,
            stake_per_agent_axon=100.0,
        )
        self.assertEqual(code, 1)

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    @mock.patch(
        "axonctl._ensure_agent_wallet",
        return_value={
            "key_id": "testkey",
            "address": "0x2222222222222222222222222222222222222222",
            "private_key": "0x" + "a" * 64,
        },
    )
    def test_funded_plan_scale_repair_status_flow(self, _wallet_mock: mock.Mock, _rpc_mock: mock.Mock) -> None:
        self.assertEqual(
            axonctl.create_request(
                state_file=str(self.state_file),
                target_agents=2,
                min_funding_axon=250.0,
                funding_address=self.valid_address,
                min_confirmations=2,
                timeout_sec=600,
                stake_per_agent_axon=100.0,
            ),
            0,
        )
        request_id = next(iter(axonctl.load_state(str(self.state_file))["requests"]))
        self.assertEqual(
            axonctl.fund_check(
                state_file=str(self.state_file),
                network=str(self.network_file),
                request_id=request_id,
                observed_amount_axon=250.0,
                observed_confirmations=3,
                observed_chain_id=8210,
                strict_rpc=True,
            ),
            0,
        )
        self.assertEqual(axonctl.build_scale_plan(str(self.state_file), str(self.network_file), str(self.agents_file), request_id), 0)
        self.assertEqual(axonctl.execute_scale(str(self.state_file), str(self.network_file), str(self.agents_file), request_id, ["agent-002"]), 0)
        after_scale = axonctl.load_state(str(self.state_file))
        self.assertIn("agent-002", after_scale["requests"][request_id]["execution"]["failed_agents"])
        self.assertEqual(axonctl.repair(str(self.state_file), request_id), 0)

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    @mock.patch(
        "axonctl._ensure_agent_wallet",
        return_value={
            "key_id": "testkey",
            "address": "0x2222222222222222222222222222222222222222",
            "private_key": "0x" + "a" * 64,
        },
    )
    def test_run_intent_pipeline_success(self, _wallet_mock: mock.Mock, _rpc_mock: mock.Mock) -> None:
        self.assertEqual(axonctl.funding_wallet_set(str(self.state_file), self.valid_address), 0)
        code = axonctl.run_intent_pipeline(
            state_file=str(self.state_file),
            network=str(self.network_file),
            agents=str(self.agents_file),
            intent="我打250 AXON，扩容2个Agents",
            funding_address=None,
            observed_confirmations=3,
            observed_chain_id=8210,
            strict_rpc=True,
        )
        self.assertEqual(code, 0)

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    @mock.patch(
        "axonctl._ensure_agent_wallet",
        return_value={
            "key_id": "testkey",
            "address": "0x2222222222222222222222222222222222222222",
            "private_key": "0x" + "a" * 64,
        },
    )
    @mock.patch("axonctl.scp_to", return_value=(True, "", ""))
    @mock.patch("axonctl.run_ssh")
    def test_remote_deploy_and_remote_status(self, ssh_mock: mock.Mock, _scp_mock: mock.Mock, _wallet_mock: mock.Mock, _rpc_mock: mock.Mock) -> None:
        self.assertEqual(
            axonctl.create_request(
                state_file=str(self.state_file),
                target_agents=2,
                min_funding_axon=250.0,
                funding_address=self.valid_address,
                min_confirmations=2,
                timeout_sec=600,
                stake_per_agent_axon=100.0,
            ),
            0,
        )
        request_id = next(iter(axonctl.load_state(str(self.state_file))["requests"]))
        self.assertEqual(
            axonctl.fund_check(
                state_file=str(self.state_file),
                network=str(self.network_file),
                request_id=request_id,
                observed_amount_axon=250.0,
                observed_confirmations=3,
                observed_chain_id=8210,
                strict_rpc=True,
            ),
            0,
        )
        self.assertEqual(axonctl.build_scale_plan(str(self.state_file), str(self.network_file), str(self.agents_file), request_id), 0)
        self.assertEqual(axonctl.execute_scale(str(self.state_file), str(self.network_file), str(self.agents_file), request_id, []), 0)
        ssh_mock.side_effect = [
            (True, "", ""),
            (True, "", ""),
            (True, "Docker version 25.0", ""),
            (True, "running", ""),
            (True, "", ""),
            (True, "running", ""),
            (True, "running", ""),
            (True, "running", ""),
        ]
        self.assertEqual(
            axonctl.remote_deploy(
                state_file=str(self.state_file),
                request_id=request_id,
                hosts_file=str(self.hosts_file),
                host_name="test-host",
                network=str(self.network_file),
                agents=str(self.agents_file),
                dry_run=False,
            ),
            0,
        )
        self.assertEqual(
            axonctl.remote_status(
                state_file=str(self.state_file),
                request_id=request_id,
                hosts_file=str(self.hosts_file),
                host_name="test-host",
            ),
            0,
        )

    @mock.patch("axonctl.run_ssh", return_value=(True, "", ""))
    def test_remote_deploy_dry_run(self, _ssh_mock: mock.Mock) -> None:
        self.assertEqual(
            axonctl.remote_deploy(
                state_file=str(self.state_file),
                request_id="dummy",
                hosts_file=str(self.hosts_file),
                host_name="test-host",
                network=str(self.network_file),
                agents=str(self.agents_file),
                dry_run=True,
            ),
            1,
        )

    def test_wallet_generate_and_list_and_export(self) -> None:
        self.assertEqual(axonctl.wallet_generate(str(self.state_file), role="funding", label="test-funding"), 0)
        self.assertEqual(axonctl.wallet_generate(str(self.state_file), role="funding", label="test-funding-2"), 0)
        self.assertEqual(axonctl.wallet_list(str(self.state_file)), 0)
        key_id = next(iter(axonctl.load_state(str(self.state_file))["wallets"]))
        self.assertEqual(axonctl.wallet_export(str(self.state_file), key_id), 0)


if __name__ == "__main__":
    unittest.main()
