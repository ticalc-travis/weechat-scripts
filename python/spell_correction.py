# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 by nils_2 <weechatter@arcor.de>
#
# a simple spell correction for a "mispelled" word
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# 2012-01-06: nils_2, (freenode.#weechat)
#       0.1 : initial release
#
# requires: WeeChat version 0.3.x
#
# Development is currently hosted at
# https://github.com/weechatter/weechat-scripts

try:
    import weechat,re, sys

except Exception:
    print("This script must be run under WeeChat.")
    print("Get WeeChat now at: http://www.weechat.org/")
    quit()

SCRIPT_NAME     = "spell_correction"
SCRIPT_AUTHOR   = "nils_2 <weechatter@arcor.de>"
SCRIPT_VERSION  = "0.1"
SCRIPT_LICENSE  = "GPL"
SCRIPT_DESC     = "a simple spell correction for a 'mispelled' word"

OPTIONS         = { 'auto_pop_up_item'       : ('off','automatic pop-up of suggestion item'),
                    'auto_replace'           : ('off','replaces misspelled word with selected suggestion, automatically'),
                    'catch_input_completion' : ('on','will catch the input_complete commands [TAB-key]'),
                  }

Hooks = {'auto_pop_up_item': '', 'catch_input_completion': '', 'catch_input_return': ''}

#multiline_input = 0
# ================================[ weechat options & description ]===============================
def init_options():
    for option,value in OPTIONS.items():
        if not weechat.config_is_set_plugin(option):
            weechat.config_set_plugin(option, value[0])
            weechat.config_set_desc_plugin(option, '%s (default: "%s")' % (value[1], value[0]))
            OPTIONS[option] = value[0]
        else:
            OPTIONS[option] = weechat.config_get_plugin(option)

def toggle_refresh(pointer, name, value):
    global OPTIONS
    option = name[len('plugins.var.python.' + SCRIPT_NAME + '.'):]        # get optionname
    OPTIONS[option] = value                                               # save new value

    if OPTIONS['auto_pop_up_item'].lower() == "off":
        if Hooks['auto_pop_up_item']:
            weechat.unhook(Hooks['auto_pop_up_item'])
    elif OPTIONS['auto_pop_up_item'].lower() == "on":
        if not Hooks['auto_pop_up_item']:
            Hooks['auto_pop_up_item'] = weechat.hook_signal ('aspell_suggest', 'aspell_suggest_cb', '')

    if OPTIONS['catch_input_completion'].lower() == "off":
        if Hooks['catch_input_completion']:
            weechat.unhook(Hooks['catch_input_completion'])
            weechat.unhook(Hooks['catch_input_return'])
    elif OPTIONS['catch_input_completion'].lower() == "on":
        if not Hooks['catch_input_completion']:
            Hooks['catch_input_return'] = weechat.hook_command_run('/input return', 'input_return_cb', '')

    return weechat.WEECHAT_RC_OK

# ================================[ hooks() ]===============================
# called from command and when TAB is pressed
def auto_suggest_cmd_cb(data, buffer, args):

    if args.lower() == 'replace':
        replace_misspelled_word(buffer)
        return weechat.WEECHAT_RC_OK

#    if not weechat.buffer_get_string(buffer,'localvar_suggest_item'):
#        return weechat.WEECHAT_RC_OK

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
    if not position:
        position = -1

    # get localvar for misspelled_word and suggestions from buffer or return
    localvar_aspell_suggest = get_localvar_aspell_suggest(buffer)
    if not localvar_aspell_suggest:
        return weechat.WEECHAT_RC_OK

    misspelled_word,aspell_suggestions = localvar_aspell_suggest.split(':')

    aspell_suggestions = aspell_suggestions.replace('/',',')
    aspell_suggestion_list = aspell_suggestions.split(',')
    if len(aspell_suggestion_list) == 0:
        position = -1
        weechat.bar_item_update('aspell_correction')
        return weechat.WEECHAT_RC_OK

    # append an empty entry to suggestions to quit without changes.
    if OPTIONS['auto_replace'].lower() == "on":
        aspell_suggestion_list.append('')

    position = int(position)
    # cycle backwards through suggestions
    if args == '/input complete_previous':
        position -= 1
        # position <= -1? go to last suggestion
        if position <= -1:
            position = len(aspell_suggestion_list)-1
    # cycle forward through suggestions
    else:
        if position >= len(aspell_suggestion_list)-1:
            position = 0
        else:
            position += 1

    # 2 = TAB or command is called
    weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:%s' % ('2',str(position),aspell_suggestion_list[position]))

#    aspell_suggest_item = aspell_suggestion_list[position]
    weechat.bar_item_update('aspell_correction')
    return weechat.WEECHAT_RC_OK

def show_item (data, item, window):

    buffer = weechat.window_get_pointer(window,"buffer")
    if buffer == '':
        return ''

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
    if not position or not aspell_suggest_item:
        return ''

    return aspell_suggest_item

# if a suggestion is selected and you edit input line, then replace misspelled word!
def input_text_changed_cb(data, signal, signal_data):

#    global multiline_input

#    if multiline_input == '1':
#        return weechat.WEECHAT_RC_OK

    buffer = signal_data
    if not buffer:
        return weechat.WEECHAT_RC_OK

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
    if not position or not aspell_suggest_item:
        return weechat.WEECHAT_RC_OK

    # 1 = cursor etc., 2 = TAB
    if tab_complete != '0':
        if not aspell_suggest_item:
            aspell_suggest_item = ''
        weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:%s' % ('0',position,aspell_suggest_item))
        weechat.bar_item_update('aspell_correction')
        return weechat.WEECHAT_RC_OK

    if OPTIONS['auto_replace'].lower() == "on":
        replace_misspelled_word(buffer) # also remove localvar_suggest_item
        return weechat.WEECHAT_RC_OK

#    weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:' % ('0','-1'))
    weechat.bar_item_update('aspell_correction')
    return weechat.WEECHAT_RC_OK

def replace_misspelled_word(buffer):
    input_line = weechat.buffer_get_string(buffer, 'input')
    localvar_aspell_suggest = get_localvar_aspell_suggest(buffer)

    if localvar_aspell_suggest:
        misspelled_word,aspell_suggestions = localvar_aspell_suggest.split(':')
        aspell_suggestions = aspell_suggestions.replace('/',',')
        aspell_suggestion_list = aspell_suggestions.split(',')
    else:
        return

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
    if not position or not aspell_suggest_item:
        return

    position = int(position)

    input_line = input_line.replace(misspelled_word, aspell_suggestion_list[position])
    if input_line[-2:] == '  ':
        input_line = input_line.rstrip()
        input_line = input_line + ' '
            
    weechat.buffer_set(buffer,'input',input_line)
    weechat.bar_item_update('aspell_correction')

    # set new cursor position. check if suggestion is longer or smaller than misspelled word
    input_pos = weechat.buffer_get_integer(buffer,'input_pos') + 1
    length_misspelled_word = len(misspelled_word)
    length_suggestion_word = len(aspell_suggestion_list[position])

    if length_misspelled_word < length_suggestion_word:
        difference = length_suggestion_word - length_misspelled_word
        new_position = input_pos + difference + 1
        weechat.buffer_set(buffer,'input_pos',str(new_position))

    weechat.buffer_set(buffer, 'localvar_del_suggest_item', '')

def get_localvar_aspell_suggest(buffer):
    return weechat.buffer_get_string(buffer, 'localvar_aspell_suggest')

def get_position_and_suggest_item(buffer):
    if weechat.buffer_get_string(buffer,'localvar_suggest_item'):
        tab_complete,position,aspell_suggest_item = weechat.buffer_get_string(buffer,'localvar_suggest_item').split(':',2)
        return (tab_complete,position,aspell_suggest_item)
    else:
        return ('','','')

def aspell_suggest_cb(data, signal, signal_data):
    buffer = signal_data
    auto_suggest_cmd_cb('', buffer, '')
    return weechat.WEECHAT_RC_OK

# this is a work-around for multiline
def multiline_cb(data, signal, signal_data):
    global multiline_input

    multiline_input = signal_data
#    if multiline_input == '1':
#        buffer = weechat.window_get_pointer(weechat.current_window(),"buffer")
#        input_line = weechat.buffer_get_string(buffer, 'input')
#    else:
#        buffer = weechat.window_get_pointer(weechat.current_window(),"buffer")
#        input_line_bak = weechat.buffer_get_string(buffer, 'input')

#        if input_line != input_line_bak:
#            input_text_changed_cb('','',buffer)

    return weechat.WEECHAT_RC_OK

# ================================[ hook_keys() ]===============================

def input_complete_cb(data, buffer, command):
#    global multiline_input

#    if multiline_input == '1':
#        multiline_input = '0'
#        return weechat.WEECHAT_RC_OK

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
    weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:%s' % ('2',position,aspell_suggest_item))

    localvar_aspell_suggest = get_localvar_aspell_suggest(buffer)
    if not localvar_aspell_suggest:
        return weechat.WEECHAT_RC_OK

    input_line = weechat.buffer_get_string(buffer, 'input')
    if not input_line:
        return weechat.WEECHAT_RC_OK

    if not weechat.config_boolean(weechat.config_get('aspell.check.real_time')):
        # real_time off
        input_pos = weechat.buffer_get_integer(buffer,'input_pos')
        input_line = input_line.decode('utf-8')
        # check cursor position
        if len(input_line) < int(input_pos):
            return weechat.WEECHAT_RC_OK
        if input_line[int(input_pos)-1] == ' ' or input_line[int(input_pos)] == ' ':
            auto_suggest_cmd_cb('', buffer, command)
        else:
            return weechat.WEECHAT_RC_OK

#    tab_complete = 1
#    if tab_complete:
#        return weechat.WEECHAT_RC_OK_EAT
    return weechat.WEECHAT_RC_OK

# if a suggestion is selected and you press [RETURN] replace misspelled word!
def input_return_cb(data, signal, signal_data):
    buffer = signal

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
    if not position or not aspell_suggest_item:
        return weechat.WEECHAT_RC_OK

    if OPTIONS['auto_replace'].lower() == "on" and aspell_suggest_item:
        replace_misspelled_word(buffer)
    
    return weechat.WEECHAT_RC_OK

def input_delete_cb(data, signal, signal_data):
    buffer = signal
    weechat.buffer_set(buffer, 'localvar_del_suggest_item', '')
    weechat.bar_item_update('aspell_correction')

#    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)
#    weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:%s' % ('1',position,aspell_suggest_item))
    return weechat.WEECHAT_RC_OK

def input_move_cb(data, signal, signal_data):
    buffer = signal

    tab_complete,position,aspell_suggest_item = get_position_and_suggest_item(buffer)

    localvar_aspell_suggest = get_localvar_aspell_suggest(buffer)
    if not localvar_aspell_suggest:
        return weechat.WEECHAT_RC_OK

    misspelled_word,aspell_suggestions = localvar_aspell_suggest.split(':')

    if not aspell_suggest_item in aspell_suggestions:
        aspell_suggestion_list = aspell_suggestions.split(',',1)
        weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:%s' % ('1',0,aspell_suggestion_list[0]))
        weechat.bar_item_update('aspell_correction')
        return weechat.WEECHAT_RC_OK

    weechat.buffer_set(buffer, 'localvar_set_suggest_item', '%s:%s:%s' % ('1',position,aspell_suggest_item))

    return weechat.WEECHAT_RC_OK
# ================================[ main ]===============================
if __name__ == "__main__":
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, '', ''):
        version = weechat.info_get("version_number", "") or 0

        if int(version) < 0x00040000:
            weechat.prnt('','%s%s %s' % (weechat.prefix('error'),SCRIPT_NAME,': needs version 0.4.0 or higher'))
            weechat.command('','/wait 1ms /python unload %s' % SCRIPT_NAME)

        weechat.hook_command(SCRIPT_NAME, SCRIPT_DESC, 'replace',
                            '\n'
                            'add item "aspell_correction" to a bar (i suggest the input bar)\n'
                            '\n'
                            'On an misspelled word, press TAB to cycle through suggestions. Any key on suggestion will replace misspelled word\n'
                            'with current suggestion.\n'
                            '\n'
                            'You have to set "aspell.check.suggestions" to a value >= 0 (default: -1 (off))\n'
                            'Using "aspell.check.real_time" the nick-completion will not work, until all misspelled words in input_line are replaced\n',
                            '',
                            'auto_suggest_cmd_cb', '')                

        init_options()

        weechat.hook_command_run('/input delete_previous_char', 'input_delete_cb', '')
        weechat.hook_command_run('/input move*', 'input_move_cb', '')
        weechat.hook_signal ('input_text_changed', 'input_text_changed_cb', '')
        # multiline workaround
#        weechat.hook_signal('input_flow_free', 'multiline_cb', '')

        weechat.bar_item_new('aspell_correction', 'show_item', '')
        if OPTIONS['auto_pop_up_item'].lower() == "on":
            Hooks['auto_pop_up_item'] = weechat.hook_signal ('aspell_suggest', 'aspell_suggest_cb', '')
        if OPTIONS['catch_input_completion'].lower() == "on":
            Hooks['catch_input_completion'] = weechat.hook_command_run('/input complete*', 'input_complete_cb', '')
            Hooks['catch_input_return'] = weechat.hook_command_run('/input return', 'input_return_cb', '')
        weechat.hook_config('plugins.var.python.' + SCRIPT_NAME + '.*', 'toggle_refresh', '')
#        weechat.prnt("","%s" % sys.version_info)