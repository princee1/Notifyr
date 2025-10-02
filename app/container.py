import asyncio
from threading import Thread
from aiorwlock import RWLock
import injector
from inspect import signature, getmro
# from dependencies import __DEPENDENCY
from typing import Callable, Any
from app.utils.constant import DependencyConstant
from app.utils.helper import issubclass_of, SkipCode
from app.utils.prettyprint import printJSON,PrettyPrinter_
from typing import TypeVar, Type
from ordered_set import OrderedSet
from app.definition._service import DEFAULT_BUILD_STATE, DEFAULT_DESTROY_STATE, PROCESS_SERVICE_REPORT, S, LiaisonDependency, LinkParams, MethodServiceNotExistsError, BaseService, AbstractDependency, AbstractServiceClasses, BuildOnlyIfDependencies, PossibleDependencies, __DEPENDENCY
import app.services
import functools

not_allowed_types=(list,str,float,bytearray,bool,bytes,int,dict,set)


class ContainerError(BaseException):
    pass


class CircularDependencyError(ContainerError):
    pass


class MultipleParameterSameDependencyError(ContainerError):
    pass


class NotSubclassOfAbstractDependencyError(ContainerError):
    pass  # The resolved class is not a subclass of the Base Class we wanted to resolve


class PrimitiveTypeError(ContainerError):
    pass


class NotBoolBuildOnlyDependencyError(ContainerError):
    pass


class NotAbstractDependencyError(ContainerError):
    pass  # Abstract Class not specified


class NoResolvedDependencyError(ContainerError):
    pass  # Cannot resolved a subclass for a parent class


class NotInDependenciesError(ContainerError):
    pass  # SubClass not in the Dependencies list


class InvalidDependencyError(ContainerError):
    pass  # Abstract class in the dependency list


def issubclass(cls): return issubclass_of(BaseService, cls)


def isabstract(cls):
    """
    The function `isabstract` checks if a class is in the set `AbstractServiceClasses`.

    :param cls: The `cls` parameter in the `isabstract` function is typically used to represent a class
    that you want to check for abstractness. The function checks if the provided class is in the
    `AbstractServiceClasses` collection to determine if it is an abstract service class
    :return: The function `isabstract(cls)` returns whether the class `cls` is contained within the set
    `AbstractServiceClasses`.
    """
    return AbstractServiceClasses.__contains__(cls)


class Container():

    def __init__(self, D: list[type],quiet=False,scopes:list[Any]=None) -> None:  # TODO add the scope option
        self.__app = injector.Injector()
        self.quiet_print = quiet

        self.DEPENDENCY_MetaData = {}
        self.__hashKeyAbsResolving: dict = {}

        self.container_lock = RWLock()

        self.__D: set[str] = self.__load_baseSet(D)
        dep_count = self.__load_dep(D)
        self.__D: OrderedSet[str] = self.__order_dependency(dep_count)
        self.D:list[Type[S]] = D

        PrettyPrinter_.show()
        PrettyPrinter_.message('Building the Container... !')
        PrettyPrinter_.space_line()

        self.__buildContainer()

    def __bind(self, type_:type, obj:Any, scope=None):
        self.__app.binder.bind(type_, to=obj, scope=scope)

    def bind(self, type_:type, obj:Any, scope=None):
        if isinstance(obj,BaseService):
            raise ValueError('Use Register Instead')
        if isinstance(obj,not_allowed_types):
            raise ValueError
        if type_ in not_allowed_types:
            raise ValueError
        self.__bind(type_, to=obj, scope=scope)
        
    def get(self, typ: Type[S] |str, scope=None, all=False) -> dict[type, Type[S]] | Type[S]:
        typ = self._str_to_service(typ)

        if not all and isabstract(typ.__name__):
            raise InvalidDependencyError

        if all and isabstract(typ.__name__):
            provider: dict[type, Type[S]] = {}
            for d in self.dependencies:
                if issubclass_of(typ, d):
                    provider[d] = self.__app.get(d, scope)
            return provider

        return self.__app.get(typ, scope)

    def _str_to_service(self, typ):
        if isinstance(typ,str):
            if not typ in self.DEPENDENCY_MetaData:
                raise NotInDependenciesError(typ)
            typ = self.DEPENDENCY_MetaData[typ][DependencyConstant.TYPE_KEY]
        return typ

    def getFromClassName(self, classname: str, scope=None):
        return self.__app.get(self.DEPENDENCY_MetaData[classname][DependencyConstant.TYPE_KEY], scope)

    def __load_dep(self, D: list[type]):
        dep_count: dict[str, int] = {}
        for x in D:
            if not self.DEPENDENCY_MetaData.__contains__(x):
                dep_param_list, p = self.getSignature(x)
                dep = set(dep_param_list)
                dep_count[x.__name__] = len(dep_param_list)

                try:
                    depNotInjected = dep.difference(self.__D)
                    if len(depNotInjected) != 0:
                        for y in depNotInjected:
                            if y not in AbstractServiceClasses:
                                raise NotInDependenciesError(y)
                    abstractRes = self.__getAbstractResolving(x)
                    for r in abstractRes.keys():
                        r_dep, r_p = self.getSignature(
                            abstractRes[r][DependencyConstant.RESOLVED_FUNC_KEY])
                        abstractRes[r][DependencyConstant.RESOLVED_PARAMETER_KEY] = r_p
                        abstractRes[r][DependencyConstant.RESOLVED_DEPS_KEY] = r_dep
                        dep = dep.union(r_dep)
                except KeyError as e:
                    pass

                try:
                    possible_dep = set(PossibleDependencies[x.__name__])
                    dep = dep.union(possible_dep)
                except KeyError:  # NOTE possible dependencies keys does not exists
                    pass
                except:
                    pass

                flag: bool = True
                try:
                    injectOnlyData = BuildOnlyIfDependencies[x.__name__]
                    flag = injectOnlyData[DependencyConstant.BUILD_ONLY_FLAG_KEY]
                    if flag is not None:
                        if flag:
                            dep.add(
                                injectOnlyData[DependencyConstant.BUILD_ONLY_CLASS_KEY])
                            raise SkipCode  # NOTE skip further line of code

                    inject_only_dep, inject_only_params = self.getSignature(
                        injectOnlyData[DependencyConstant.BUILD_ONLY_FUNC_KEY])
                    injectOnlyData[DependencyConstant.BUILD_ONLY_DEP_KEY] = inject_only_dep
                    injectOnlyData[DependencyConstant.BUILD_ONLY_PARAMS_KEY] = inject_only_params
                    dep = dep.union(set(inject_only_dep))
                except SkipCode as e:
                    pass
                except:
                    pass

                self.DEPENDENCY_MetaData[x.__name__] = {
                    DependencyConstant.TYPE_KEY: x,
                    DependencyConstant.DEP_KEY: dep,
                    DependencyConstant.PARAM_NAMES_KEY: p,
                    DependencyConstant.DEP_PARAMS_KEY: dep_param_list,
                    # NOTE the flag might be None, if it is indeed i need to check the func
                    DependencyConstant.FLAG_BUILD_KEY: flag
                }

        return dep_count

    def __filter(self, D: list[type]):
        temp: list[type] = []
        for dep in D:
            try:
                if issubclass(dep):
                    temp.append(dep)
                else:
                    raise TypeError
            except:  # catch certain type of error
                pass

        return temp

    def __getAbstractResolving(self, typ: type):
        return AbstractDependency[typ.__name__]

    def getSignature(self, t: type | Callable):
        params = signature(t).parameters.values()
        types: list[str] = []
        paramNames: list[str] = []
        for p in params:
            if types.count(p.annotation.__name__) == 1:
                raise MultipleParameterSameDependencyError

            types.append(p.annotation.__name__)
            paramNames.append(p.name)

        return types, paramNames

    def __load_baseSet(self, D: list[type]):
        t: set[str] = set()
        for d in D:
            if isabstract(d.__name__):
                raise InvalidDependencyError
            t.add(d.__name__)
        return t
    
    def __add_dep(self, D:list[type]|type):
        D = [D] if not isinstance(D,list) else D
        set_d = self.__load_baseSet(D)
        self.__D.update(set_d)

    def __buildContainer(self):
        D = self.__D.copy()
        while D.__len__() != 0:
            no_dep = []
            for x in D:
                d: set[str] = self.DEPENDENCY_MetaData[x][DependencyConstant.DEP_KEY]
                if len(d.intersection(D)) == 0:
                    no_dep.append(x)
            if len(no_dep) == 0:
                raise CircularDependencyError
            D.difference_update(no_dep)
            for x in no_dep:
                self.__inject(x)

    def __inject(self, x: str):
        current_type: type = self.DEPENDENCY_MetaData[x][DependencyConstant.TYPE_KEY]
        if isabstract(current_type):
            return
        dep: list[str] = self.DEPENDENCY_MetaData[x][DependencyConstant.DEP_PARAMS_KEY]
        params_names: list[str] = self.DEPENDENCY_MetaData[x][DependencyConstant.PARAM_NAMES_KEY]
        # VERIFY the number of dependency
        if AbstractDependency.__contains__(x) or self.__searchParentClassAbstractDependency(current_type):
            self.__resolvedAbsDep(current_type)
            dep = self.__switchAbsDep(current_type, dep)
        # BUG might need to call before the abstract resolving
        self.__resolve_buildOnly(x)
        params = self.toParams(dep, params_names)
        obj = self.__createDep(current_type, params)
        self.__bind(current_type, obj)

    def __order_dependency(self, dep_count):
        temp_dep_list = list(self.__D)
        ordered_dependencies = sorted(
            temp_dep_list, key=lambda x: dep_count[x])
        del temp_dep_list
        return OrderedSet(ordered_dependencies)

    def __resolve_buildOnly(self, dep_name: str):
        if dep_name in BuildOnlyIfDependencies and BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_FLAG_KEY] is None:
            func = BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_FUNC_KEY]
            bOnlyDep, bOnlyParamNames = self.getSignature(func)
            BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_DEP_KEY] = bOnlyDep
            BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_PARAMS_KEY] = bOnlyParamNames
            params = self.toParams(bOnlyDep, bOnlyParamNames)
            flag = func(**params)
            if type(flag) != bool:
                raise NotBoolBuildOnlyDependencyError
            self.DEPENDENCY_MetaData[dep_name][DependencyConstant.FLAG_BUILD_KEY] = flag

    def __searchParentClassAbstractDependency(self, currentType: type):
        parentClasses: list[type] = list(getmro(currentType))
        parentClasses.pop(0)
        for x in parentClasses:
            if x.__name__ in AbstractDependency.keys():
                self.__hashKeyAbsResolving[currentType.__name__] = x
                return True
        return False
        # for x in AbstractDependency:
        #     absDepKeyClass = AbstractModuleClasses[x]
        #     if issubclass_of( absDepKeyClass,currentType):
        #         self.hashKeyAbsResolving[currentType.__name__] = x
        #         return True
        # return False

    def __switchAbsDep(self, current_type: type, dependencies: list[str]):
        if len(dependencies) == 0:
            return []
        try:
            for absClassname, resolvedClass in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                if resolvedClass[DependencyConstant.RESOLVED_CLASS_KEY]:
                    index = dependencies.index(absClassname)
                    del dependencies[index]
                    dependencies.insert(
                        index, resolvedClass[DependencyConstant.RESOLVED_CLASS_KEY].__name__)
            return dependencies
        except ValueError as e:
            pass
        except KeyError as e:
            # BUG: handle the case where the dependency cannot be resolved
            pass

    def __resolvedAbsDep(self, current_type: type):
        try:
            if issubclass(current_type):
                pass
            for absClassName, absResolving in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                absClass = AbstractServiceClasses[absClassName]
                if not isabstract(absClass):
                    raise NotAbstractDependencyError
                absResParams = {}
                if absResolving[DependencyConstant.RESOLVED_PARAMETER_KEY] is not None:
                    absResParams = self.toParams(
                        absResolving[DependencyConstant.RESOLVED_DEPS_KEY], absResolving[DependencyConstant.RESOLVED_PARAMETER_KEY])

                resolvedDep = absResolving[DependencyConstant.RESOLVED_FUNC_KEY](
                    **absResParams)
                if not isinstance(resolvedDep, type):
                    raise TypeError  # suppose to be an instance of type

                if not issubclass_of(absClass, resolvedDep):
                    raise NotSubclassOfAbstractDependencyError

                if not issubclass(resolvedDep):
                    # WARNING: This might create problem
                    pass
                absResolving[DependencyConstant.RESOLVED_CLASS_KEY] = resolvedDep

        except NameError:
            pass
        except TypeError:
            pass
        except KeyError:
            pass
        return current_type

    def toParams(self, dep, params_names):
        try:
            params = {}
            for i,d in enumerate(dep):
                obj_dep = self.get(self.DEPENDENCY_MetaData[d][DependencyConstant.TYPE_KEY])
                params[params_names[i]] = obj_dep
            return params
        except KeyError as e :
            raise NoResolvedDependencyError(e.args)

    def __createDep(self, typ: type, params:dict[str,S]):
        flag = issubclass(typ)
        obj: BaseService = typ(**params)
        
        if flag:
            dep_services = {}

            for s in params.values():
                c = s.__class__ 
                dep_services[c]=s
                s.used_by_services[obj.__class__] = obj
            
            obj.dependant_services= dep_services
            willBuild = self.DEPENDENCY_MetaData[typ.__name__][DependencyConstant.FLAG_BUILD_KEY]
            if willBuild:
                obj._builder()  # create the dependency but not calling the builder
        else:
            # WARNING raise we cant verify the data provided
            pass

        return obj

    def need(self, typ: Type[S]) -> Type[S]:
        typ = self._str_to_service(typ)

        if not self.DEPENDENCY_MetaData[typ.__name__][DependencyConstant.BUILD_ONLY_FLAG_KEY]:
            dependency: Type[S] = self.get(typ)
            try:
                dependency._builder()
                self.DEPENDENCY_MetaData[typ.__name__][DependencyConstant.BUILD_ONLY_FLAG_KEY] = True
                return dependency
            except:
                pass
        return self.get(typ)

    def destroyAllDependency(self, scope=None):
        for dep in self.D:
            dep._destroyer()

    def destroyDep(self, typ: type, scope=None,all=False,rebuild:bool = True):
        
        dependency = self.get(typ, scope,all=all)
        cache = {}

        def __destroy(dep:BaseService,linkParams:LinkParams={}):
            print(dep.name)

            if dep.name in cache:
                return 
            
            if linkParams.get('destroy_follow_dep',True):
                dep._destroyer(destroy_state=linkParams.get('destroy_state',DEFAULT_DESTROY_STATE))
            if rebuild and linkParams.get('rebuild',False):
                dep._builder(build_state=linkParams.get('build_state',DEFAULT_BUILD_STATE),force_sync_verify=True)

            cache[dep.name] = True
            
            for x in dep.used_by_services.values():
                if x.name in cache:
                    continue
                linkP =  LiaisonDependency[x.name]
                linkP = linkP[dep.__class__]
                __destroy(x,linkParams=linkP)
        
        if all: 
            for d in dependency.values():
                __destroy(d)
        else:
            __destroy(d)
               
    def reloadDep(self, typ: type, scope=None,all=True,bypass_destroy=False):

        s:dict[str,BaseService] |BaseService =self.get(typ,scope,False,all)
        
        cache = {}
        def __reload(service:BaseService,link_params:LinkParams={}):
            print(service.name)

            if service.name in cache:
                return 
            
            if not bypass_destroy and link_params.get('to_destroy',False):
                service._destroyer(destroy_state=link_params.get('build_state',DEFAULT_DESTROY_STATE))
            
            if link_params.get('to_build',False):
                service._builder(build_state=link_params.get('build_state',DEFAULT_BUILD_STATE),force_sync_verify=True)

            cache[service.name] = True
            
            for used_s in service.used_by_services.values():
                if used_s.name in cache:
                    continue

                linkP =  LiaisonDependency[used_s.name]
                linkP = linkP[service.__class__]
                __reload(used_s,linkP)

        if all:
            for all_s in s.values():
                __reload(all_s)
        else:
            __reload(s)
        
    def register_new_dep(self,typ:type,scope= None):
        self.__add_dep([typ])
        self.__load_dep([typ])
        self.__inject(typ.__name__)
    
    def show_dep_graph(self):
        for d in self.D:
            s:BaseService= self.get(d)
            PrettyPrinter_.info(f"=================================== {s.name} ===================================",saveable=False)
            PrettyPrinter_.json(s.used_by_services ,saveable=False)

    def show_report(self):
       PrettyPrinter_.json(PROCESS_SERVICE_REPORT,saveable=False)

    @property
    def dependencies(self) -> list[BaseService]: return [x[DependencyConstant.TYPE_KEY]
                                                  for x in self.DEPENDENCY_MetaData.values()]

    @property
    def objectDependencies(self):
        return [self.get(d) for d in self.dependencies]

    @property
    def hashAbsDep(self, cls: str):
        return cls if not self.__hashKeyAbsResolving.__contains__(cls) else self.__hashKeyAbsResolving[cls]

    @property
    def seek_bindings(self):
        return self.__app.binder._bindings

    @property
    def services_status(self):
        return {s:s.service_status for s in self.dependencies}


CONTAINER: Container = None #Container(__DEPENDENCY)

def build_container(quiet=False,dep=__DEPENDENCY):
    PrettyPrinter_.quiet=quiet
    global CONTAINER
    CONTAINER = Container(dep)

def InjectInFunction(func: Callable):
    """
    The `InjectInFunction` decorator takes the function and inspect it's signature, if the `CONTAINER` can resolve the 
    dependency it will inject the values otherwise it will throw a `NoResolvedDependencyError`. You can call the function with the position parameter 
    format to call the `func` with the rest of the parameters set to the default value or with a value as needed.It means that you have to define it the __init__
    function all parameter needed to be resolved by the `CONTAINER` before the other parameter as well

    If the parameters of the function founds a dependency two times it will return an error

    :param func: The function to decorates

    :throw NoResolvedDependencyError:
    :throw MultipleDependenciesError:

    :return Callable: The function decorated and injected with the value from the `CONTAINER`

    `example::`

    @InjectInFunction
    \ndef test(a: A, b: B, c: C, s:str):\n
        print(a)
        print(b)
        print(c)
        print(s)

    \n
    >>> test(s="ok")
    >>> <__main__.C object at 0x000001A76EC36610>
        <__main__.B object at 0x000001A76EC36810>
        <__main__.A object at 0x000001A76EC3FB90>
        ok
    """
    types, paramNames = CONTAINER.getSignature(func)  # ERROR if theres is other parameter that is not in dependencies
    paramsToInject = CONTAINER.toParams(types, paramNames)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        paramsToInject.update(kwargs)
        return func(**paramsToInject)
    return wrapper


def InjectInMethod(func: Callable):
    """
    The `InjectInConstructor` decorator takes the __init__ function from a class and inspect it's signature, if the `CONTAINER` can resolve the 
    dependency it will inject the values otherwise it will throw a `NoResolvedDependencyError`. You must call the function with the position parameter 
    format to call the `func` with the rest of the parameters set to the default value or with a value as needed. It means that you have to define it the __init__
    function all parameter needed to be resolved by the `CONTAINER` before the other parameter as well

    If the parameters of the function founds a dependency two times it will return an error

    :param func: The method function from a class

    :throw NoResolvedDependencyError:
    :throw MultipleDependenciesError:

    :return Callable: The method function decorated and injected with the value from the `CONTAINER`

    `example::`

    class Test:

    @InjectInConstructor\n

    def __init__(self, configService:ConfigService, securityService:SecurityService,test:str=None):
        self.configService = configService
        self.securityService = securityService
        self.test = test\n
        print(configService)
        print(securityService)
        print(test)


    >>> Test()
    >>> Service: ConfigService Hash: 124165042117
        Service: SecurityService Hash: 124166930269
        None

    >>> Test(test="Hello")
    >>> Service: ConfigService Hash: 124165042117
        Service: SecurityService Hash: 124166930269
        Hello

    >>> Test("Allo")
    >>> TypeError: Test.__init__() missing 2 required positional arguments: 'securityService' and 'test'

    """
    types, paramNames = CONTAINER.getSignature(func) # ERROR if the function is not a method and if theres is other parameter that is not in depencies
    del types[0]
    del paramNames[0]
    paramsToInject = CONTAINER.toParams(types, paramNames)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        paramsToInject.update(kwargs)
        return func(*args, **paramsToInject)
    return wrapper

def Injectable(scope: Any |None = None ):
    def class_decorator(cls:type) -> type:
        return cls
    return class_decorator

def Get(typ: Type[S]|str, scope=None, all=False) -> dict[str, Type[S]] | Type[S]:
    """
    The `Get` function retrieves a service from a container based on the specified type, scope, and
    whether to retrieve all instances if it`s an AbstractService  [or in a multibind context].

    :param typ: The `typ` parameter is the type of service that you want to retrieve from the container.
    :type typ: type[Service]

    :param scope: The `scope` parameter in the `Get` function is used to specify the scope within which
    the service should be retrieved. It allows you to narrow down the search for the service based on a
    specific scope or context. If no scope is provided, the function may retrieve the service from a
    broader scope

    :param all: The `all` parameter in the `Get` function is a boolean flag that specifies whether to
    retrieve all instances of the specified service type or just a single instance. 
    :return: The function `Get` is returning the service object of calling the `get` method on the `CONTAINER`
    object with the specified parameters `typ`, `scope`, and `all`.
    """
    return CONTAINER.get(typ, scope=scope, all=all)

def Register(typ:Type[S],scope=None)->Type[S]:
    CONTAINER.register_new_dep(typ,scope)
    return Get(typ,scope)

def Need(typ: Type[S]|str) -> Type[S]:
    """
    The function `Need` takes a type parameter `Service` and returns the result of calling the `need`
    method on the `CONTAINER` object with the specified type.
    """
    return CONTAINER.need(typ)


def Bind(type_:type, obj:Any, scope=None):
    return CONTAINER.bind(type_,obj,scope)

def GetDepends(typ:type[S])->Type[S] | dict[str,Type[S]]:
    def depends():
        return Get(typ)
    return depends

def GetDependsFunc(typ:type[S],func_name:str)->Callable:
    self = Get(typ)
    func = getattr(self,func_name,None)
    if not func:
        raise MethodServiceNotExistsError
    
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def depends(**kwargs):
            return await func(**kwargs)
    else:
        @functools.wraps(func)
        def depends(**kwargs):
            return func(**kwargs)
    
    return depends

def GetAttr(typ:type[S],attr_name:str):
    self = Get(typ)
    return getattr(self,attr_name,None)

