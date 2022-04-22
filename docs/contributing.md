## Contributing Code

We'd love to accept your patches and contributions to this project. There are a just a few
small guidelines you need to follow.

1.   It's generally best to starting a new thread on vpp-dev@lists.fd.io in which you describe
     the bug you're intending to fix, or the feature you're intending to add. Even if you think
     it's relatively minor, it's helpful to know what people are working on. Mention in your mail
     that you are planning to work on that bug or feature so that it can be attributed to you.
1.   Follow the normal process of cloning the project, and setup a new branch to work in. It's
     important that each group of changes be done in separate branches in order to ensure that a
     pull request only includes the commits related to that bug or feature. 
     *NOTE*: We follow VPP's general contribution workflow described [here](https://wiki.fd.io/view/VPP/Pulling,_Building,_Running,_Hacking_and_Pushing_VPP_Code)
1.   Any significant changes should always be accompanied by tests. The project already has good
     test coverage, so look at some of the existing tests if you're unsure how to go about it.
     Particularly relevant are config syntax and semantic validation, which will be expected to
     have (a) full test coverage and (b) not negatively impact other configuration elements. If
     in doubt, discuss the trade-offs on the mailinglist first.
1.   All contributions must be licensed Apache 2.0 and all source code files must have a copy of
     the boilerplate licence comment with author and copyright attribution. 'Signed-off-by' field
     is required for all contributions, signalling Developer Certificate of Origin 1.1 (commonly
     used by VPP and originally from the Linux kernel).
1.   Do your best to have well-formed commit messages for each change. This provides consistency
     throughout the project, and ensures that commit messages are able to be formatted properly
     by various git tools.
1.   Code will be checked for Python formatting by [black](https://github.com/psf/black) so before
     submitting a pull request (or pushing), ensure `black . vppcfg` is run and changes are accounted
     for.

Finally, push the commits to your fork and submit a pull request (GitHub) or commit them to
gerrit.fd.io and request a review (Gerrit).

```
Developer's Certificate of Origin 1.1

    By making a contribution to this project, I certify that:

    (a) The contribution was created in whole or in part by me and I
        have the right to submit it under the open source license
        indicated in the file; or

    (b) The contribution is based upon previous work that, to the best
        of my knowledge, is covered under an appropriate open source
        license and I have the right under that license to submit that
        work with modifications, whether created in whole or in part
        by me, under the same open source license (unless I am
        permitted to submit under a different license), as indicated
        in the file; or

    (c) The contribution was provided directly to me by some other
        person who certified (a), (b) or (c) and I have not modified
        it.

    (d) I understand and agree that this project and the contribution
        are public and that a record of the contribution (including all
        personal information I submit with it, including my sign-off) is
        maintained indefinitely and may be redistributed consistent with
        this project or the open source license(s) involved.
```

### Completeness

Feature additions are expected to be reasonably complete when merged. Keep work-in-progress in
a git branch until it's completed. New VPP APIs should have:

*   A config schema and semantic validation (`vppcfg check`)
*   A config reader (`vppcfg dump`)
*   A config planner (`vppcfg plan`)
*   A config applier (`vppcfg apply`)
*   A reasonable N-way integration test (moving between various YAML configuration states without
    crashing `vppcfg` or VPP itself)
*   Demonstrably work well with existing code.

### Testing Requirements

`vppcfg` will be used in many different scenarios - from the bench just doing a quick test
when hacking on a VPP feature, all the way through to large production networks where dataplane
crashes cause user harm. As such, contributing code has to be done with care.

Static analysis is incredibly important, to help ensure that the YAML configuration files can
be safely applied to running VPP instances:

*   All changes to syntax validation are expected to have 100% unit test coverage.
*   All changes to semantic validation are expected to have 100% YAMLTest coverage.
*   New code cannot break an existing test unless the test is objectively incorrect.

APIs integrations that require hardware, for example DPDK, RDMA or other custom hardware, are very
welcome in `vppcfg`. However, they must be tested / testable as well, so hardware must be made
available to testing rigs either remotely or locally, and integrated with release and integration
testing harnass to ensure continued support in releases. Contact the project tech lead to coordinate.

### Version Skew

`vppcfg` is intended to work within two major releases of VPP. For example, 21.10 and 22.02 will
be supported until 22.06 releases, after which 21.10 will no longer be supported and `vppcfg`
will print a warning. Best effort will be applied to ensuring that `vppcfg` works at each major
release window, in other words when VPP 22.06 releases, it is expected that `vppcfg` will pass
all unit- and regression/integration tests upon its release. It will then be tagged (and in the
future, likely released in tandem with VPP itself).

Workarounds in the `vppcfg` code will be tolerated within this two major releases time window.
To avoid technical debt, features will be asked to sync-to-latest when they have workarounds,
TODOs and special-cases that are VPP-version dependent, and they are eligable for removal if
they do not keep up with HEAD.

*NOTE*: Support is unlikely to be tractable in the case of any WARNING/ERROR states noted by
`vppcfg`. The API controlsurface of VPP is considerable, and at times `vppcfg` takes an opinionated
stance by recommending against configuration patterns even if they are strictly valid in VPP
(for example, setting an MTU on a BVI different to the bridge member interfaces). Operators
and code contributions should be strict in their semantic validation, with the intent of making
errors/bugs/crashes less likely in production.
