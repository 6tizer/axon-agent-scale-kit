import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))
import axonctl  # noqa: E402


class AxonCtlRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.network_file = self.base / "network.yaml"
        self.agents_file = self.base / "agents.yaml"
        self.state_file = self.base / "state.json"
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
        self.valid_address = "0x1111111111111111111111111111111111111111"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    def test_validate_passes_with_standard_network(self, _rpc_mock: mock.Mock) -> None:
        code = axonctl.validate(str(self.network_file), str(self.agents_file), strict_rpc=True)
        self.assertEqual(code, 0)

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
    def test_funded_plan_scale_repair_status_flow(self, _rpc_mock: mock.Mock) -> None:
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
        state = axonctl.load_state(str(self.state_file))
        request_id = next(iter(state["requests"]))
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
        self.assertEqual(
            axonctl.execute_scale(
                state_file=str(self.state_file),
                network=str(self.network_file),
                agents=str(self.agents_file),
                request_id=request_id,
                fail_agents=["agent-002"],
            ),
            0,
        )
        after_scale = axonctl.load_state(str(self.state_file))
        failed = after_scale["requests"][request_id]["execution"]["failed_agents"]
        self.assertIn("agent-002", failed)
        self.assertEqual(axonctl.repair(str(self.state_file), request_id), 0)
        final_state = axonctl.load_state(str(self.state_file))
        self.assertEqual(final_state["requests"][request_id]["execution"]["failed_agents"], {})
        self.assertEqual(final_state["requests"][request_id]["status"], "SCALED")

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    def test_run_intent_pipeline_success(self, _rpc_mock: mock.Mock) -> None:
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
        state = axonctl.load_state(str(self.state_file))
        req = state["requests"][sorted(state["requests"].keys())[-1]]
        self.assertEqual(req["target_agents"], 2)
        self.assertIn(req["status"], {"SCALED", "SUCCESS"})

    @mock.patch("axonctl.rpc_chain_id", return_value=(True, 8210, None))
    def test_run_intent_pipeline_requires_initialized_funding_wallet(self, _rpc_mock: mock.Mock) -> None:
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
        self.assertEqual(code, 1)

    def test_funding_wallet_set_and_get(self) -> None:
        self.assertEqual(axonctl.funding_wallet_set(str(self.state_file), self.valid_address), 0)
        self.assertEqual(axonctl.funding_wallet_get(str(self.state_file)), 0)

    def test_run_intent_pipeline_rejects_invalid_sentence(self) -> None:
        self.assertEqual(axonctl.funding_wallet_set(str(self.state_file), self.valid_address), 0)
        code = axonctl.run_intent_pipeline(
            state_file=str(self.state_file),
            network=str(self.network_file),
            agents=str(self.agents_file),
            intent="请帮我处理一下",
            funding_address=None,
            observed_confirmations=3,
            observed_chain_id=8210,
            strict_rpc=False,
        )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
