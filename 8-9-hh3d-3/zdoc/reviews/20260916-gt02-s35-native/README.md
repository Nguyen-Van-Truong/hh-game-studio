# S35 actual AppContainer counter transport

Status: diagnostic evidence, **not acceptance**. Final run is
`GT02-S35-NATIVE-03`; earlier runs 01/02 and their exact probe sources remain.
Source closure: `264ed3e3f35ca76038ba20cc00f41f3345ba6e9352e111b3be5e7ed38fe6e111`.
The complete 73-file snapshot was checked before/after execution; 13 loaded
`studio.*` modules map to that snapshot. This runs the new endpoint and
fixture dispatcher, not the older S33 prototype.

Six fixed C AppContainer cases exercised real work/control pipes: submit,
wrong session token, stale lease, lost reply, Cancel and Stop. Every case has
native start/completion markers, host-captured exit 57, Job active count zero
and no remaining child PID. Submit/lost-reply read back value 101, revision 1,
one effect, and the same receipt on HTTP retry. Invalid token/lease, Cancel
and Stop leave zero effects. Work/control are bound to the retained live
process PID/creation time; the endpoint queries the primary AppContainer
token, package SID, user, session, Low integrity and zero capabilities.

Each actual worker also received access denied (5) for pipe WRITE_DAC,
WRITE_OWNER and a second pipe instance. A separate negative case connected
an ordinary process while binding a different, suspended AppContainer;
kernel client-PID readback differed and admission failed before dispatch.
That placeholder was never resumed and was deliberately terminated (125)
for cleanup; it is not one of the six successful application runs.

The native executable uses pinned MSVC/SDK compile inputs, `/W4 /WX /MT`.
Its hash is `3fbf25e19321adf35c3a25809fcc7d048c07be3e799abd1e779f30b4ea6a4dfd`.
The owned profile, package mapping, temporary directory and runtime snapshot
were removed; endpoint/I/O owner registries ended at zero. No global TEMP or
unrelated-process cleanup claim is made. Test credentials remain local to
launch; published responses/logs contain no credential.

`manifest.json` binds 14 source/log artifacts and two frozen S32 compiler/API
dependencies. `verify_package.py` pins its manifest hash, verifies all three
capture chains and final semantic/native readback, and also checks ignored
local raw output/executable when available. Portable Git copies explicitly
report raw data unavailable; they still verify published hashes and content.
Verifier/README are Git metadata outside the manifest to avoid circular hashes.

```powershell
python -O 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s35-native/verify_package.py
```

Run 01 proved the six cases on source-hashed modules. Run 02 added the full
snapshot and wrong-PID case. Run 03 additionally binds the actually loaded
module paths/hashes and independent kernel PID readback. Existing evidence
was extended with distinct runs, not overwritten.

Pre-freeze diagnostics found Windows canonical SDDL adds the `AI` SACL flag;
the endpoint now authors the observed canonical descriptor and still compares
exactly. A unit fixture trying to mutate DACL from a client WRITE_DAC handle
received error 5. The final tamper unit instead gives its owned server fixture
WRITE_DAC, actually changes that server's DACL and checks rejection. Neither
diagnostic is promoted to independent sandbox evidence.

This is a fixed counter, with a trusted supervisor owning process/endpoint
lifecycle. It does not publish private staged files, implement durable active
selection or reconcile engine consumers. Public safe_write/atomic_replace
remain false. There are no independent critic signatures for this closure.

Primary references: [named-pipe client PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid),
[primary token query](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation),
[SDDL control flags](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-string-format).
