## Design

### Validators

Validators are functions which are passed the fully formed YAML configuration and are meant to
check it for syntax and semantic validity. A validator has a unique name and takes the (yaml)
configuration as the only argument. Validators are expected to return a tuple of (bool,[string])
where the boolean signals success (False meaning the validator rejected the configuration file,
True meaning it is known to be correct), and a list of zero or more strings which contain messages
meant for human consumption. They can contain INFO, WARN or ERROR messages, and are meant to help
the caller understand why the validator rejected the configuration.

Validators can be disabled with the --skip-validator &lt;name&gt; [&lt;name&gt;] flag. It is not
advised to skip validators. The purpose of the validators is to ensure the configuration is sane
and semantically correct.

Validators can be registered as follows:
