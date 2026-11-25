"""Non-gameplay visual showcase; no save or RNG changes."""
from . import cli
from .cinematic import Animator, View, UnitView
from .sprites import HEROES


def gallery():
    ui=cli.UI; animator=Animator(ui); keys=list(HEROES)
    while True:
        rows=[f'[{i+1}] {name:<12} | {HEROES[name].style.upper()}' for i,name in enumerate(keys)]
        ui.screen('Motion gallery',ui.panel('CHOOSE CLASS',rows+['[A] Play all  [X] Back']), 'Preview only; no gameplay or checkpoint changes.')
        c=cli.choose('Preview',set('1234567AX'))
        if c=='X': return
        selected=keys if c=='A' else [keys[int(c)-1]]
        for name in selected:
            before=View({-1:UnitView('Preview',name,30,30,0,(1,3)),0:UnitView('Skeleton','Skeleton',20,20,0,(3,3))},5,1,'ongoing',10,10,18)
            after=View({-1:before.units[-1],0:UnitView('Skeleton','Skeleton',14,20,0,(3,3))},3,1,'ongoing',10,10,18)
            if animator.enabled:
                animator.sequence(before,after,-1,0,name+' / DEMO','attack')
            else:
                from .sprites import pose
                sprite=HEROES[name]
                rows=[]
                for state in ('idle','ready','strike','walk','guard','hurt','down'):
                    rows += [state.upper(),*pose(sprite,state)]
                ui.screen('Motion gallery',ui.panel(name,rows),'Static pose sheet: animations require an ANSI terminal.')
                ui.pause()
        if animator.enabled: ui.pause('Enter untuk kembali ke gallery')
