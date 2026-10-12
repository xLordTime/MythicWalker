# Derived from Deimos-Wizard101, d7ef56eb51c5b5316cadba40ca554ec442a5dcee. GPL-3.0.
# Game actions are supplied by MythicWalker; no Python eval/exec is used.
from __future__ import annotations
from .types import *
class VMError(ValueError): pass
class ExpressionVM:

    async def eval(self, expression: Expression, client: Client | None=None):
        match expression:
            case IdentExpression():
                return expression.ident
            case ConstantReferenceExpression():
                if expression.name in self._constants:
                    return self._constants[expression.name]
                raise VMError(f'Unknown constant: ${expression.name}')
            case ConstantCheckExpression():
                constant_name = expression.name
                if expression.value is None:
                    if constant_name in self._constants:
                        return self._constants[constant_name]
                    raise VMError(f'Unknown constant: {constant_name}')
                expected_value = await self.eval(expression.value)
                if constant_name in self._constants:
                    actual_value = self._constants[constant_name]
                    if isinstance(expected_value, bool) and isinstance(actual_value, str):
                        if actual_value.lower() == 'true':
                            actual_value = True
                        elif actual_value.lower() == 'false':
                            actual_value = False
                    return actual_value == expected_value
                return False
            case RangeMinExpression():
                range_value = await self.eval(expression.range_expr, client)
                if isinstance(range_value, str):
                    try:
                        min_val, _ = map(float, range_value.split('-'))
                        return min_val
                    except ValueError:
                        raise VMError(f"Invalid range format: {range_value}. Expected format like '1-100'")
                else:
                    raise VMError(f'Range expression must evaluate to a string, got {range_value}')
            case RangeMaxExpression():
                range_value = await self.eval(expression.range_expr, client)
                if isinstance(range_value, str):
                    try:
                        _, max_val = map(float, range_value.split('-'))
                        return max_val
                    except ValueError:
                        raise VMError(f"Invalid range format: {range_value}. Expected format like '1-100'")
                else:
                    raise VMError(f'Range expression must evaluate to a string, got {range_value}')
            case IndexAccessExpression():
                container = await self.eval(expression.expr, client)
                index = await self.eval(expression.index, client)
                if isinstance(container, list) and isinstance(index, (int, float)):
                    index_int = int(index)
                    if 0 <= index_int < len(container):
                        return container[index_int]
                    else:
                        return 0.0
                else:
                    return 0.0
            case AndExpression():
                for expr in expression.expressions:
                    if not await self.eval(expr, client):
                        return False
                return True
            case OrExpression():
                for expr in expression.expressions:
                    if await self.eval(expr, client):
                        return True
                return False
            case CommandExpression():
                return await self._eval_command_expression(expression)
            case NumberExpression():
                return expression.number
            case XYZExpression():
                return XYZ(await self.eval(expression.x, client), await self.eval(expression.y, client), await self.eval(expression.z, client))
            case UnaryExpression():
                match expression.operator.kind:
                    case TokenKind.minus:
                        result = await self.eval(expression.expr, client)
                        return -result
                    case TokenKind.keyword_not:
                        expr_result = await self.eval(expression.expr, client)
                        if isinstance(expression.expr, CommandExpression) and expression.expr.command.player_selector.any_player:
                            current_matches = self._any_player_client.copy()
                            self._any_player_client = [c for c in self._clients if c not in current_matches]
                        return not expr_result
                    case _:
                        raise VMError(f'Unimplemented unary expression: {expression}')
            case StringExpression():
                return expression.string
            case StrFormatExpression():
                format_str = expression.format_str
                values = []
                for eval in expression.values:
                    result = await self.eval(eval, client)
                    values.append(result)
                return format_str % tuple(values)
            case KeyExpression():
                key = expression.key
                if key not in Keycode.__members__:
                    raise VMError(f'Unknown key code: {key}')
                return Keycode[expression.key]
            case EquivalentExpression():
                left = await self.eval(expression.lhs, client)
                right = await self.eval(expression.rhs, client)
                if isinstance(left, list) and len(left) > 0:
                    left = left[0]
                if isinstance(right, list) and len(right) > 0:
                    right = right[0]
                return left == right
            case DivideExpression():
                left = await self.eval(expression.lhs, client)
                right = await self.eval(expression.rhs, client)
                return left / right
            case GreaterExpression():
                left = await self.eval(expression.lhs, client)
                right = await self.eval(expression.rhs, client)
                if isinstance(left, list) and len(left) > 0:
                    left = left[0]
                if isinstance(right, list) and len(right) > 0:
                    right = right[0]
                return left > right
            case Eval():
                return await self._eval_expression(expression, client)
            case SelectorGroup():
                players = self._select_players(expression.players)
                expr = expression.expr
                if expression.players.any_player:
                    self._any_player_client = []
                    found_any = False
                    for anyplayer in self._clients:
                        result = await self.eval(expr, anyplayer)
                        if result:
                            self._any_player_client.append(anyplayer)
                            found_any = True
                    return found_any
                else:
                    for player in players:
                        if not await self.eval(expr, player):
                            return False
                    return True
            case ReadVarExpr():
                loc = await self.eval(expression.loc)
                assert loc != None and type(loc) == int
                test = self.current_task.stack[loc]
                return test
            case StackLocExpression():
                return expression.offset
            case SubExpression():
                lhs = await self.eval(expression.lhs, client)
                rhs = await self.eval(expression.rhs, client)
                assert isinstance(lhs, (int, float))
                assert isinstance(rhs, (int, float))
                return lhs - rhs
            case ListExpression():
                result = []
                if hasattr(expression, 'items') and isinstance(expression.items, list):
                    for item in expression.items:
                        evaluated_item = await self.eval(item, client)
                        if isinstance(evaluated_item, list):
                            result.extend(evaluated_item)
                        else:
                            result.append(evaluated_item)
                elif hasattr(expression, 'items') and isinstance(expression.items, ListExpression):
                    inner_result = await self.eval(expression.items, client)
                    result = inner_result if isinstance(inner_result, list) else [inner_result]
                elif hasattr(expression, 'expr') and isinstance(expression.expr, ListExpression):
                    inner_result = await self.eval(expression.expr, client)
                    result = inner_result if isinstance(inner_result, list) else [inner_result]
                elif hasattr(expression, 'expr'):
                    single_result = await self.eval(expression.expr, client)
                    result = [single_result]
                return result
            case ContainsStringExpression():
                lhs = await self.eval(expression.lhs, client)
                rhs = await self.eval(expression.rhs, client)
                if isinstance(rhs, list):
                    return any((item in lhs for item in rhs))
                return rhs in lhs
            case _:
                raise VMError(f'Unimplemented expression type: {expression}')
