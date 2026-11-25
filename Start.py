import sys
if __name__ == '__main__':
    if '--classic' in sys.argv:
        sys.argv.remove('--classic')
        from rpg.cli import main
    else:
        from rpg.procedural_cli import main
    main()
