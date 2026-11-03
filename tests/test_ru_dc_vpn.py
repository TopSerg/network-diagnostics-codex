"""Offline regression checks for the existing operational VPN runner."""
import tempfile
import contextlib
import io
import json
import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import ru_dc_vpn as runner
from mikenopa_utils.network_ssh import Credentials


class PublicationCliTests(unittest.TestCase):
    def invoke(self, arguments):
        with patch('sys.argv', ['ru_dc_vpn.py', *arguments]), contextlib.redirect_stderr(io.StringIO()):
            return runpy.run_path(str(Path(runner.__file__)), run_name='__main__')

    def test_no_private_defaults_or_implicit_target(self):
        with self.assertRaises(SystemExit) as error:
            self.invoke(['read', '--command', '/system identity print'])
        self.assertEqual(error.exception.code, 2)

    def test_duplicate_inventory_target_stops_before_prompt_or_auth(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            book = Workbook()
            book.active.append(['ip', 'controlName', 'model'])
            for _ in range(2):
                book.active.append(['192.0.2.10', 'fixture-router', 'MikroTik'])
            book.save(root / 'inventory.xlsx')
            book.close()
            (root / 'trust.json').write_text(json.dumps({'192.0.2.10': 'SHA256:fixture'}))
            with patch('getpass.getpass') as prompt, \
                 patch('mikenopa_utils.network_ssh.connect_xnet_then_radius') as connect:
                with self.assertRaises(SystemExit) as error:
                    self.invoke(['read', '--inventory', str(root / 'inventory.xlsx'),
                                 '--trust', str(root / 'trust.json'), '--output-dir', str(root / 'operation'),
                                 '--host', '192.0.2.10', '--label', 'identity', '--prompt-password',
                                 '--command', '/system identity print'])
                self.assertEqual(error.exception.code, 2)
            prompt.assert_not_called()
            connect.assert_not_called()

    def test_hidden_input_never_falls_back_to_echo(self):
        import getpass
        import warnings
        from mikenopa_utils.credential_input import prompt_secret
        def unavailable(*args):
            warnings.warn('synthetic echo unavailable', getpass.GetPassWarning)
        with patch('getpass.getpass', side_effect=unavailable):
            with self.assertRaisesRegex(ValueError, 'Hidden input unavailable'):
                prompt_secret('Synthetic input')


class OperationalRunnerAuthTests(unittest.TestCase):
    def test_routeros_custom_guard_error_is_recognized(self):
        self.assertTrue(runner.routeros_command_error('Input anchor is not unique (:error; line 1)\n'))
        self.assertTrue(runner.routeros_command_error('no such item (/ip/firewall/nat/add; line 1)\n'))
        self.assertFalse(runner.routeros_command_error('state=established\n'))

    def test_routeros_guard_error_stops_before_the_next_command(self):
        client = Mock()
        stdout = Mock()
        stdout.read.return_value = b'STOP fixture (:error; line 1)\n'
        stderr = Mock()
        stderr.read.return_value = b''
        client.exec_command.return_value = (Mock(), stdout, stderr)
        with patch.object(runner, 'connect', return_value=client), patch.object(runner, 'devices', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'Stopped after RouterOS'):
                runner.run({'model':'MikroTik'}, [':error fixture', '/ip route add dst-address=192.0.2.0/24 gateway=192.0.2.1'], 'guard', stop_on_error=True)
        self.assertEqual(client.exec_command.call_count, 1)

    def test_configuration_line_ending_hash_is_not_the_device_prompt(self):
        channel = Mock(closed=False)
        channel.recv_ready.return_value = True
        channel.recv.side_effect = [b'banner motd #', b'\r\nfixture/pri/act(config)#']
        result = runner.read_cli(channel, expected_base='fixture/pri/act')
        self.assertTrue(result.endswith('fixture/pri/act(config)#'))

    def test_cli_waits_through_a_gap_longer_than_old_idle_timeout(self):
        channel = Mock(closed=False)
        channel.recv_ready.side_effect = [False, False, True, True]
        channel.recv.side_effect = [b'show clock\r\n19:00:00 MSK\r\n', b'fixture/pri/act#']
        with patch.object(runner.time, 'monotonic', side_effect=[0, .1, 1.5, 1.6, 1.7]), patch.object(runner.time, 'sleep'):
            result = runner.read_cli(channel)
        self.assertIn('fixture/pri/act#', result)

    def test_cli_recognizes_split_password_and_ansi_prompt(self):
        channel = Mock(closed=False)
        channel.recv_ready.return_value = True
        channel.recv.side_effect = [b'enable\r\nPass', b'word: ']
        self.assertTrue(runner.read_cli(channel, allow_password=True).endswith('word: '))
        channel.recv.side_effect = [b'\x1b[0mfixture(config-if)#\x1b[0m']
        self.assertIn('fixture(config-if)#', runner.read_cli(channel))

    def test_cli_timeout_retains_partial_without_claiming_success(self):
        channel = Mock(closed=False)
        channel.recv_ready.return_value = True
        channel.recv.return_value = b'incomplete output'
        with patch.object(runner.time, 'monotonic', side_effect=[0, 1, 36]):
            with self.assertRaises(runner.CLIReadTimeout) as error:
                runner.read_cli(channel)
        self.assertEqual(error.exception.partial, 'incomplete output')

    def test_encoded_hidden_transport_preserves_punctuation_and_case(self):
        fixture = 'Abcd@efGhij1'
        self.assertEqual(runner.decode_prompt_password(fixture.encode('utf-8').hex(), 'hex'), fixture)

    def test_plain_hidden_input_is_unchanged(self):
        self.assertEqual(runner.decode_prompt_password('fixture'), 'fixture')

    def test_invalid_encoded_input_fails_without_echoing_it(self):
        for value in ('', 'zz', '1', 'ff', '0a', '00', '61620d'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^Invalid encoded password input$'):
                runner.decode_prompt_password(value, 'hex')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name, value in {
            'FOLDER': Path(self.temp.name), 'AUTH_EVENTS': [],
            'TRUST': {'192.0.2.10': 'SHA256:fixture', '[192.0.2.10]:2222': 'SHA256:fixture'},
            'RADIUS_PROVIDER': Mock(cached=None), 'EXTRA_SECRETS': [],
        }.items():
            replacement = patch.object(runner, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.device = {'ip': '192.0.2.10', 'login': 'fixture-local', 'password': 'fixture-password'}

    def test_normal_path_uses_shared_policy_and_records_auth_source(self):
        client = Mock()
        def connected(host, local, pins, provider, *, attempts, port):
            self.assertEqual(local, Credentials('fixture-local', 'fixture-password'))
            self.assertEqual(port, 22)
            attempts.append({'source': 'xnet', 'status': 'authenticated'})
            return client, 'xnet'
        with patch.object(runner, 'connect_xnet_then_radius', side_effect=connected):
            self.assertIs(runner.connect(self.device), client)
        journal = (runner.FOLDER / 'AUTH_STATUS.json').read_text()
        self.assertIn('authenticated', journal)
        self.assertNotIn('fixture-password', journal)

    def test_missing_local_is_not_converted_into_string_credentials(self):
        with patch.object(runner, 'connect_xnet_then_radius', return_value=(Mock(), 'radius')) as connect:
            runner.connect({'ip': '192.0.2.10', 'login': None, 'password': None})
        self.assertIsNone(connect.call_args.args[1])

    def test_exact_alternate_port_is_passed_to_shared_transport(self):
        with patch.object(runner, 'connect_xnet_then_radius', return_value=(Mock(), 'xnet')) as connect:
            runner.connect({**self.device, '_connect_port': 2222})
        self.assertEqual(connect.call_args.kwargs['port'], 2222)

    def test_unknown_key_blocks_before_authentication(self):
        with patch.object(runner, 'connect_xnet_then_radius') as connect:
            with self.assertRaisesRegex(RuntimeError, 'credentials withheld'):
                runner.connect({**self.device, 'ip': '192.0.2.11'})
        connect.assert_not_called()

    def test_failed_transport_still_records_auth_status(self):
        def blocked(*args, attempts, **kwargs):
            attempts.append({'source': 'xnet', 'status': 'blocked'})
            raise TimeoutError('fixture timeout')
        with patch.object(runner, 'connect_xnet_then_radius', side_effect=blocked):
            with self.assertRaises(TimeoutError):
                runner.connect(self.device)
        self.assertIn('blocked', (runner.FOLDER / 'AUTH_STATUS.json').read_text())

    def test_redaction_covers_url_inventory_and_radius_secrets(self):
        runner.RADIUS_PROVIDER.cached = Credentials('fixture-radius', 'fixture-radius-password')
        raw = ('https://example.test/?pass=url-fixture&token=token-fixture\n'
               'snmp-server host inside 192.0.2.1 version 2c other-community\n'
               'username fixture password unrelated-password encrypted\n'
               ' key other-key-fixture\nntp authentication-key 7 md5 ntp-fixture\n'
               'fixture-radius-password inventory-community\n'
               'route outside 0.0.0.0 0.0.0.0 192.0.2.1\n')
        with patch.object(runner, 'devices', return_value=[{'snmpCommunityRead': 'inventory-community'}]):
            result = runner.clean(raw)
        for secret in ('url-fixture', 'token-fixture', 'other-community', 'unrelated-password',
                       'fixture-radius-password', 'inventory-community', 'other-key-fixture', 'ntp-fixture'):
            self.assertNotIn(secret, result)
        self.assertIn('route outside 0.0.0.0 0.0.0.0 192.0.2.1', result)


if __name__ == '__main__':
    unittest.main()
