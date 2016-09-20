#!/usr/bin/env python
from utils import cliparser
from core.channel import Channel
from utils.loggers import log
from core.checks import Checks

version = '0.2'

def main():
    
    args = vars(cliparser.options)
    
    if not args.get('url'):
        cliparser.parser.error('URL is required. Run with -h for help.')
        
    # Add version
    args['version'] = version
    
    checks = Checks(Channel(args))
    checks.check_template_injection()
    
if __name__ == '__main__':

    log.info(cliparser.banner % version)
    
    try:
        main()
    except (KeyboardInterrupt):
        log.info('Exiting.')
    except Exception as e:
        log.critical('Exiting: %s' % e)
        raise
