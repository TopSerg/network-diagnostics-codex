"""Synthetic, offline auth-order and host-identity regression tests."""
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import paramiko
from paramiko.ssh_exception import BadAuthenticationType, PartialAuthentication
from mikenopa_utils.network_ssh import (Credentials, CredentialsUnavailable, HostKeyError,
    RadiusProvider, AuthenticationChallengeError, PasswordAuthentication, PasswordOnlyTransport, KeyboardInteractiveTransport,
    connect_xnet_then_radius, fingerprint, load_policy)


class Key:
    def asbytes(self):return b'synthetic-public-host-key'


class Client:
    def __init__(self, outcome=None, key=None):
        self.outcome=outcome;self.key=key or Key();self.closed=False;self.calls=[]
    def set_missing_host_key_policy(self, policy):self.policy=policy
    def connect(self, host, **kwargs):
        self.policy.missing_host_key(self,host,self.key)
        self.calls.append(kwargs)
        if self.outcome:raise self.outcome
    def close(self):self.closed=True
    def get_transport(self):
        transport=Mock();transport.is_authenticated.return_value=True;return transport


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.host='192.0.2.10';self.pins={self.host:fingerprint(Key())}
        self.local=Credentials('fixture-local','fixture-local-password')
        self.radius=Mock(return_value=Credentials('fixture-radius','fixture-radius-password'))
        self.policy=load_policy();self.attempts=[]
    def connect(self, clients, **kwargs):
        return connect_xnet_then_radius(self.host,self.local,self.pins,self.radius,
            policy=self.policy,attempts=self.attempts,client_factory=Mock(side_effect=clients),**kwargs)
    def test_local_success_does_not_access_radius(self):
        local=Client();client,source=self.connect([local])
        self.assertIs(client,local);self.assertEqual(source,'xnet');self.radius.assert_not_called()
        self.assertFalse(local.calls[0]['allow_agent']);self.assertFalse(local.calls[0]['look_for_keys'])
        self.assertEqual(local.calls[0]['password'],self.local.password)
        self.assertNotIn('auth_strategy',local.calls[0])
    def test_explicit_primary_interactive_does_not_change_fallback_transport(self):
        local=Client(paramiko.AuthenticationException('Rejected'));radius=Client()
        client,source=self.connect([local,radius],local_keyboard_interactive=True)
        self.assertIs(local.calls[0]['transport_factory'],KeyboardInteractiveTransport)
        self.assertIs(radius.calls[0]['transport_factory'],PasswordOnlyTransport)
        self.assertIs(client,radius);self.assertEqual(source,'radius')
    def test_rejection_then_radius_and_failed_session_closed(self):
        local=Client(paramiko.AuthenticationException('Rejected'));radius=Client()
        client,source=self.connect([local,radius])
        self.assertTrue(local.closed);self.assertIs(client,radius);self.assertEqual(source,'radius')
        self.assertEqual([x['source'] for x in self.attempts],['xnet','radius'])
        self.assertEqual(local.calls[0]['username'],'fixture-local')
        self.assertEqual(radius.calls[0]['username'],'fixture-radius')
        self.assertNotIn('password',json.dumps(self.attempts))
    def test_both_rejected_only_two_attempts(self):
        clients=[Client(paramiko.AuthenticationException('Rejected')) for _ in range(2)]
        with self.assertRaises(paramiko.AuthenticationException):self.connect(clients)
        self.assertTrue(all(x.closed for x in clients));self.assertEqual(len(self.attempts),2)
    def test_transport_and_auth_timeout_and_partial_do_not_fallback(self):
        for error in (socket.timeout(),paramiko.SSHException('Banner error'),
                      paramiko.AuthenticationException('Authentication timeout.'),
                      PartialAuthentication(['keyboard-interactive'])):
            with self.subTest(error=type(error).__name__):
                client=Client(error)
                with self.assertRaises(type(error)):self.connect([client])
                self.assertTrue(client.closed);self.radius.assert_not_called()
    def test_missing_pin_creates_no_client(self):
        factory=Mock()
        with self.assertRaises(HostKeyError):
            connect_xnet_then_radius(self.host,self.local,{},self.radius,client_factory=factory)
        factory.assert_not_called();self.radius.assert_not_called()
    def test_changed_key_blocks_before_password_is_sent(self):
        class OtherKey:
            def asbytes(self):return b'changed-synthetic-key'
        client=Client(key=OtherKey())
        with self.assertRaises(HostKeyError):self.connect([client])
        self.assertEqual(client.calls,[]);self.assertTrue(client.closed);self.radius.assert_not_called()
    def test_key_checked_again_before_radius_authentication(self):
        local=Client(paramiko.AuthenticationException('Rejected'));radius=Client()
        radius.key=Mock();radius.key.asbytes.return_value=b'changed-synthetic-key'
        with self.assertRaises(HostKeyError):self.connect([local,radius])
        self.assertEqual(radius.calls,[]);self.assertTrue(radius.closed)
    def test_same_operation_recovery_does_not_repeat_rejected_local(self):
        radius=Client();_,source=self.connect([radius],local_rejected=True)
        self.assertEqual(source,'radius');self.assertEqual(len(radius.calls),1)
    def test_missing_local_can_use_radius(self):
        client=Client()
        _,source=connect_xnet_then_radius(self.host,None,self.pins,self.radius,
            client_factory=lambda:client)
        self.assertEqual(source,'radius');self.assertEqual(client.calls[0]['username'],'fixture-radius')
    def test_credentials_repr_and_policy_have_no_secret(self):
        self.assertNotIn('fixture-local',repr(self.local))
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'policy.json';bad=load_policy();bad['auth_order']=['radius','xnet']
            p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):load_policy(p)
            bad=load_policy();bad['radius']['password']='fixture-only-password';p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):load_policy(p)
    def test_provider_is_lazy_and_uses_process_cache(self):
        with patch.dict('os.environ',{},clear=True),patch('mikenopa_utils.network_ssh.read_radius_credential',return_value=self.local) as read:
            provider=RadiusProvider(self.policy);read.assert_not_called()
            self.assertIs(provider(),self.local);self.assertIs(provider(),self.local);read.assert_called_once()
    def test_incomplete_environment_does_not_silently_switch_sources(self):
        with patch.dict('os.environ',{'MIKENOPA_RADIUS_USERNAME':'fixture-user'},clear=True):
            with self.assertRaises(CredentialsUnavailable):RadiusProvider(self.policy)()
    def test_password_strategy_does_not_enable_implicit_challenge_fallback(self):
        transport=Mock();transport.is_authenticated.return_value=True
        PasswordAuthentication(self.local).authenticate(transport)
        transport.auth_password.assert_called_once_with(self.local.username,self.local.password,fallback=False)
    def test_one_plain_password_challenge_is_supported(self):
        transport=Mock();transport.is_authenticated.return_value=True
        transport.auth_password.side_effect=BadAuthenticationType('Unsupported',['keyboard-interactive'])
        transport.auth_interactive.side_effect=lambda username,handler: self.assertEqual(handler('','',[('Password: ',False)]),[self.local.password])
        PasswordAuthentication(self.local).authenticate(transport)
    def test_otp_or_password_change_challenge_is_not_answered(self):
        for prompt in ('OTP:','New password:','Old password:'):
            transport=Mock();transport.auth_password.side_effect=BadAuthenticationType('Unsupported',['keyboard-interactive'])
            transport.auth_interactive.side_effect=lambda username,handler: handler('','',[(prompt,False)])
            with self.assertRaises(AuthenticationChallengeError):PasswordAuthentication(self.local).authenticate(transport)
    def test_partially_authenticated_strategy_stops(self):
        transport=Mock();transport.is_authenticated.return_value=False;transport.auth_password.return_value=['keyboard-interactive']
        with self.assertRaises(PartialAuthentication):PasswordAuthentication(self.local).authenticate(transport)
    def test_legacy_interactive_flow_allows_empty_challenge_but_one_password(self):
        transport=object.__new__(PasswordOnlyTransport)
        def exchange(self,username,handler,submethods):
            self_test.assertEqual(handler('','',[]),[])
            self_test.assertEqual(handler('','',[('Password:',False)]),['fixture-only-response'])
            self_test.assertEqual(handler('','',[]),[])
            with self_test.assertRaises(AuthenticationChallengeError):handler('','',[('Password:',False)])
        self_test=self
        with patch.object(paramiko.Transport,'auth_interactive',exchange):
            transport.auth_interactive('fixture-user',lambda *args:['fixture-only-response'])
    def test_explicit_interactive_method_keeps_the_challenge_guard(self):
        transport=object.__new__(KeyboardInteractiveTransport)
        def exchange(self,username,handler,submethods):
            self_test.assertEqual(handler('','',[]),[])
            self_test.assertEqual(handler('','',[('Password:',False)]),['fixture-only-password'])
            with self_test.assertRaises(AuthenticationChallengeError):handler('','',[('OTP:',False)])
            return []
        self_test=self
        with patch.object(paramiko.Transport,'auth_interactive',exchange):
            transport.auth_password('fixture-user','fixture-only-password')
    def test_disconnect_is_unknown_and_does_not_trigger_radius(self):
        client=Client(paramiko.AuthenticationException('Authentication failed.'))
        transport=Mock();transport.is_active.return_value=False
        client.get_transport=lambda:transport
        with self.assertRaises(paramiko.AuthenticationException):self.connect([client])
        self.radius.assert_not_called();self.assertEqual(self.attempts[-1]['status'],'incomplete')


if __name__=='__main__':unittest.main()
