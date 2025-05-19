package com.example.labelMark.controller;

import cn.hutool.core.util.ObjectUtil;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.domain.SysUser;
import com.example.labelMark.domain.Task;
import com.example.labelMark.domain.TaskDatasetInfo;
import com.example.labelMark.domain.Type;
import com.example.labelMark.service.MarkService;
import com.example.labelMark.service.SysUserService;
import com.example.labelMark.service.TaskAcceptedService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.service.TypeService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.LoginUser;
import com.example.labelMark.vo.TaskInfoDTO;
import com.example.labelMark.vo.constant.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import io.swagger.models.auth.In;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import javax.validation.constraints.Pattern;
import java.util.*;
import java.util.stream.Collectors;

import static com.example.labelMark.utils.CoordinateConverter.convertGeojson;

/**
 * <p>
 * 前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@RestController
@RequestMapping("/task")
@Api(tags = "TASK业务控制器")
public class TaskController {

    @Resource
    private TaskService taskService;
    @Resource
    private TypeService typeService;
    @Resource
    private SysUserService sysUserService;
    @Resource
    private TaskAcceptedService taskAcceptedService;
    @Resource
    private MarkService markService;


    @PostMapping("/createTask")
    @ApiOperation("创建任务")
    public Result createTask(String dataRange, String taskName, String taskType, String mapServer) {
        // 获取当前登录用户信息
        LoginUser loginUser = (LoginUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        SysUser currentUser = loginUser.getSysUser();
        int isSucceed = taskService.createTask(dataRange, taskName, taskType, mapServer, currentUser.getUserid(), 0);
        if (isSucceed != -1) {
            return ResultGenerator.getSuccessResult("插入成功");
        }
        return ResultGenerator.getSuccessResult("插入失败");
    }

    @PostMapping("/publishTask")
    @ApiOperation("创建任务,包括保存关联的指定任务用户和类型")
    public Result publishTask(@RequestBody Map<String, Object> map) {
        // 获取当前登录用户信息
        LoginUser loginUser = (LoginUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        SysUser currentUser = loginUser.getSysUser();
        Integer creatorUserId = currentUser.getUserid();
        Integer teamId = currentUser.getTeamId();
        
        ArrayList<String> dateRange = (ArrayList<String>) map.get("daterange");
        String taskName = map.get("taskname").toString();
        String taskType = map.get("type").toString();
        String mapServer = map.get("mapserver").toString();
        String dateRangeStr = dateRange.get(0) + " " + dateRange.get(1);
        
        // 获取目标用户类型和对应的数据
        String targetUserType = map.get("targetUserType").toString(); // allTeamMembers, specificTeamUsers, allNonTeamUsers
        int taskClass = 0; // 默认为团队相关
        
        // 检查用户权限，普通用户只能指定"所有非管理员用户"
        if (currentUser.getIsadmin() == 0) {
            // 普通用户只能将任务分配给所有非管理员用户
            targetUserType = "allNonAdminUsers";
            taskClass = 1; // 非团队相关
        } else {
            // 管理员可以按照前端选择的目标用户类型处理
            // 根据目标用户类型设置任务的class值
            if ("allNonTeamUsers".equals(targetUserType)) {
                taskClass = 1; // 非团队相关
            }
        }
        
        // 创建任务
        int taskId = taskService.createTask(dateRangeStr, taskName, taskType, mapServer, creatorUserId, taskClass);
        if (taskId == -1) {
            return ResultGenerator.getFailResult("插入任务失败");
        }
        
        List<SysUser> targetUsers = new ArrayList<>();
        
        // 普通用户处理逻辑
        if (currentUser.getIsadmin() == 0) {
            // 获取所有非管理员用户
            targetUsers = sysUserService.getAllNonAdminUsers();
            
            // 获取统一分配的样本类型
            List<?> rawSelectedSampleTypes = (List<?>) map.get("selectedSampleTypes");
            List<String> selectedSampleTypes = new ArrayList<>();
            
            // 将所有的样本类型转换为String
            if (rawSelectedSampleTypes != null) {
                for (Object type : rawSelectedSampleTypes) {
                    selectedSampleTypes.add(String.valueOf(type));
                }
            }
            
            // 为每个用户创建task_accepted记录，分配相同的样本类型
            for (SysUser user : targetUsers) {
                String typeStr = String.join(",", selectedSampleTypes);
                boolean success = taskAcceptedService.createTaskAccept(taskId, user.getUsername(), typeStr);
                if (!success) {
                    return ResultGenerator.getFailResult("为非管理员用户分配任务失败");
                }
            }
        }
        // 管理员处理逻辑
        else {
            // 根据目标用户类型决定用户列表和样本类型
            if ("allTeamMembers".equals(targetUserType)) {
                // 获取所有团队成员（除管理员外）
                targetUsers = sysUserService.getUsersByTeamIdAndNotAdmin(teamId);
                // 获取统一分配的样本类型
                List<?> rawSelectedSampleTypes = (List<?>) map.get("selectedSampleTypes");
                List<String> selectedSampleTypes = new ArrayList<>();
                
                // 将所有的样本类型转换为String
                if (rawSelectedSampleTypes != null) {
                    for (Object type : rawSelectedSampleTypes) {
                        selectedSampleTypes.add(String.valueOf(type));
                    }
                }
                
                // 为每个用户创建task_accepted记录，分配相同的样本类型
                for (SysUser user : targetUsers) {
                    String typeStr = String.join(",", selectedSampleTypes);
                    boolean success = taskAcceptedService.createTaskAccept(taskId, user.getUsername(), typeStr);
                    if (!success) {
                        return ResultGenerator.getFailResult("为团队成员分配任务失败");
                    }
                }
                
            } else if ("allNonTeamUsers".equals(targetUserType)) {
                // 获取所有非团队成员（除管理员外）
                targetUsers = sysUserService.getNonTeamUsersAndNotAdmin(teamId);
                // 获取统一分配的样本类型
                List<?> rawSelectedSampleTypes = (List<?>) map.get("selectedSampleTypes");
                List<String> selectedSampleTypes = new ArrayList<>();
                
                // 将所有的样本类型转换为String
                if (rawSelectedSampleTypes != null) {
                    for (Object type : rawSelectedSampleTypes) {
                        selectedSampleTypes.add(String.valueOf(type));
                    }
                }
                
                // 为每个用户创建task_accepted记录，分配相同的样本类型
                for (SysUser user : targetUsers) {
                    String typeStr = String.join(",", selectedSampleTypes);
                    boolean success = taskAcceptedService.createTaskAccept(taskId, user.getUsername(), typeStr);
                    if (!success) {
                        return ResultGenerator.getFailResult("为非团队用户分配任务失败");
                    }
                }
                
            } else if ("specificTeamUsers".equals(targetUserType)) {
                // 获取从前端传来的特定用户分配信息
                ArrayList<Map<String, Object>> specificUserAssignments = 
                    (ArrayList<Map<String, Object>>) map.get("specificUserAssignments");
                
                // 处理每个特定用户的分配
                for (Map<String, Object> assignment : specificUserAssignments) {
                    String username = assignment.get("username").toString();
                    List<?> rawTypeArr = (List<?>) assignment.get("typeArr");
                    List<String> typeStrList = new ArrayList<>();
                    
                    // 将所有类型转换为String
                    if (rawTypeArr != null) {
                        for (Object type : rawTypeArr) {
                            typeStrList.add(String.valueOf(type));
                        }
                    }
                    
                    String typeStr = String.join(",", typeStrList);
                    
                    boolean success = taskAcceptedService.createTaskAccept(taskId, username, typeStr);
                    if (!success) {
                        return ResultGenerator.getFailResult("为特定用户分配任务失败");
                    }
                }
            } else {
                return ResultGenerator.getFailResult("无效的目标用户类型");
            }
        }
        
        return ResultGenerator.getSuccessResult("任务创建成功");
    }

    @GetMapping("/getTaskInfo")
    @ApiOperation("获取任务")
    public Map<String, Object> getTaskInfo(@RequestParam(required = false) Integer taskid,
                                           @RequestParam(required = false) Integer current,
                                           @RequestParam(required = false) Integer pageSize,
                                           @RequestParam(required = false) String taskname,
                                           @RequestParam(required = false) String userArr,
                                           @RequestParam(required = false) Integer isAdmin) {

        // 获取当前登录用户信息
        LoginUser loginUser = (LoginUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        SysUser currentUser = loginUser.getSysUser();
        Integer requestingUserId = currentUser.getUserid();
        Integer userId = currentUser.getUserid();

        // 无参时默认值
        if (ObjectUtil.isEmpty(current)) {
            current = 1;
        }
        if (ObjectUtil.isEmpty(pageSize)) {
            pageSize = 5;
        }

        List<TaskInfoDTO> result = new ArrayList<>();
        int taskCount = 0;

        // 无论是普通用户还是管理员，都只能看到自己创建的任务
        result = taskService.getTasksByCreatorId(requestingUserId);
        taskCount = result.size();

        // 补充用户和类型信息
        for (TaskInfoDTO taskInfo : result) {
            int taskId = taskInfo.getTaskid();

            // 获取任务相关的用户信息
            List<Map<String, Object>> userArrOrigin = new ArrayList<>();
            List<String> usernames = taskService.findUserListByTaskId(taskId);

            for (String username : usernames) {
                SysUser user = sysUserService.findByUsername(username);
                if (user != null) {
                    // 获取分配给该用户的类型
                    String typeString = taskAcceptedService.getTypeArrByTaskIdAndUsername(taskId, username);
                    List<Type> typeArr = new ArrayList<>();

                    if (typeString != null && !typeString.isEmpty()) {
                        List<Integer> typeIds = Arrays.stream(typeString.split(","))
                                .map(Integer::parseInt)
                                .collect(Collectors.toList());

                        for (Integer typeId : typeIds) {
                            String typeName = typeService.getTypeNameById(typeId);
                            List<Type> types = typeService.getTypes(current, pageSize, typeId, typeName);
                            if (!types.isEmpty()) {
                                typeArr.add(types.get(0));
                            }
                        }
                    }

                    Map<String, Object> info = new HashMap<>();
                    info.put("userid", user.getUserid());
                    info.put("username", user.getUsername());
                    info.put("typeArr", typeArr);
                    userArrOrigin.add(info);
                }
            }

            taskInfo.setUserArr(userArrOrigin);
        }

        // 特定任务ID过滤
        if (taskid != null) {
            result = result.stream()
                    .filter(item -> taskid.equals(item.getTaskid()))
                    .collect(Collectors.toList());
        }

        // 模糊查询：按任务名
        if (taskname != null && !taskname.isEmpty()) {
            result = result.stream()
                    .filter(item -> item.getTaskname().contains(taskname))
                    .collect(Collectors.toList());
        }

        List<Mark> marks = new ArrayList<>();
        if (taskid != null) {
            marks = markService.getMarkByTaskId(taskid);
        }

        // 计算起始索引和结束索引，实现分页
        int startIndex = (current - 1) * pageSize;
        int endIndex = Math.min(startIndex + pageSize, result.size());

        // 防止索引越界
        if (startIndex < result.size()) {
            result = result.subList(startIndex, endIndex);
        } else {
            result = new ArrayList<>();
        }

        Map<String, Object> response = new HashMap<>();
        response.put("code", 200);
        response.put("data", result);
        response.put("success", true);
        response.put("markGeoJsonArr", convertGeojson(marks));
        response.put("total", taskCount);
        return response;
    }

    @PutMapping("/updateTask")
    public Result updateTask(@RequestBody Map<String, Object> map) {
        ArrayList<String> dateRange = (ArrayList<String>) map.get("daterange");
        String taskName = map.get("taskname").toString();
        String taskType = map.get("type").toString();
        ArrayList<String> usernameAndTypeArr = (ArrayList<String>) map.get("userArr");
        String mapServer = map.get("mapserver").toString();
        Integer taskId = Integer.valueOf(map.get("taskid").toString());
//        拼接起止日期
        String dateRangeStr = dateRange.get(0) + " " + dateRange.get(1);

        taskService.updateTaskById(taskId, taskName, dateRangeStr, taskType, mapServer);

        //        拆解用户和所属类型
        String username, typeArr = "";
        for (String usernameAndType : usernameAndTypeArr) {
            String[] usernameAndTypeStr = usernameAndType.split(",");
            username = usernameAndTypeStr[0];
            for (int i = 1; i < usernameAndTypeStr.length; i++) {
                if (i == usernameAndTypeStr.length - 1) {
                    typeArr += usernameAndTypeStr[i];
                } else {
                    typeArr += usernameAndTypeStr[i] + ",";
                }
            }
            boolean isUpdate = taskAcceptedService.createTaskAccept(taskId, username, typeArr);
//            重置
            typeArr = "";
            if (isUpdate == false) {
                return ResultGenerator.getSuccessResult("插入接收任务失败");
            }
        }
        return ResultGenerator.getSuccessResult("任务更新成功");
        }

    @DeleteMapping("/deleteTask/{taskId}")
    public Result deleteTask(@PathVariable int taskId) {
        taskAcceptedService.deleteTaskAcceptByTaskId(taskId);
        taskService.deleteTaskById(taskId);
        markService.deleteMarkByTaskId(taskId);
        return ResultGenerator.getSuccessResult("任务删除成功");
    }

    @PostMapping("/submitTask")
    public Result submitTask(@RequestBody Map<String, Object> map) {
        Integer taskId = (Integer) map.get("taskid");
        if (markService.GetTaskIdNum(taskId) == 0) {
            return ResultGenerator.getFailResult("未开始标注");
        }
        taskService.updateTaskStatus(taskId);
        return ResultGenerator.getSuccessResult("任务提交成功，审核中");
    }

    @PostMapping("/auditTask")
    public Result auditTask(@RequestBody Map<String, Object> map) {
        String audit_feedback = ObjectUtil.toString(map.get("auditfeedback"));
        Integer status = Integer.valueOf(ObjectUtil.toString(map.get("status")));
        Integer taskId = Integer.valueOf(ObjectUtil.toString(map.get("taskid")));
        taskService.auditTask(taskId, status, audit_feedback);
        return ResultGenerator.getSuccessResult("编辑任务完成，提交成功");
    }

    @GetMapping("/getPersonalTaskList")
    @ApiOperation("获取分配给当前用户的任务列表")
    public Map<String, Object> getPersonalTaskList(@RequestParam(required = false) Integer taskid,
                                           @RequestParam(required = false) Integer current,
                                           @RequestParam(required = false) Integer pageSize,
                                           @RequestParam(required = false) String taskname) {

        // 获取当前登录用户信息
        LoginUser loginUser = (LoginUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        SysUser currentUser = loginUser.getSysUser();
        String username = currentUser.getUsername();
        Integer userId = currentUser.getUserid();
        // 无参时默认值
        if (ObjectUtil.isEmpty(current)) {
            current = 1;
        }
        if (ObjectUtil.isEmpty(pageSize)) {
            pageSize = 5;
        }

        // 获取分配给当前用户的任务
        List<TaskInfoDTO> list = taskService.getTaskInfo(username);
        int taskCount = list.size();

        List<TaskInfoDTO> result = new ArrayList<>();

        // 处理任务信息
        for (TaskInfoDTO taskInfo : list) {
            // 标记已经存在的同一任务taskInfo对象
            TaskInfoDTO existingObj = null;
            int index = -1;
            for (int i = 0; i < result.size(); i++) {
                if (ObjectUtil.equals(result.get(i).getTaskid(), taskInfo.getTaskid())) {
                    existingObj = result.get(i);
                    index = i;
                }
            }
            // 处理typestring得到有效信息
            String typestring = taskInfo.getTypeArr();
            // 标注地图时才需要遍历标签方案
            List<Integer> type = new ArrayList<>();
            if (typestring != null && !typestring.isEmpty()) {
                type = Arrays.stream(typestring.split(","))
                        .map(Integer::parseInt)
                        .collect(Collectors.toList());
            }
            List<Type> typeArr = new ArrayList<>();
            if (ObjectUtil.isNotNull(taskInfo.getTaskid())) {
                for (Integer typeId : type) {
                    String typeName = typeService.getTypeNameById(typeId);
                    List<Type> types = typeService.getTypes(current, pageSize, typeId, typeName);
                    typeArr.add(types.get(0));
                }
            }
            Map<String, Object> info = new HashMap<>();
            info.put("userid", taskInfo.getUserid());
            info.put("username", taskInfo.getUsername());
            info.put("id", taskInfo.getId());
            info.put("typeArr", typeArr);
            if (existingObj != null) {
                // 如果已经存在，直接将用户信息添加到 userArr 数组中
                List<Map<String, Object>> userArrOrigin = existingObj.getUserArr();
                userArrOrigin.add(info);
                taskInfo.setUserArr(userArrOrigin);
                // 确保保留taskClass值
                taskInfo.setTaskClass(existingObj.getTaskClass());
                result.set(index, taskInfo);
            } else {
                List<Map<String, Object>> userArrOrigin = new ArrayList<>();
                userArrOrigin.add(info);
                taskInfo.setUserArr(userArrOrigin);
                // 确保从数据库获取的taskClass值已经设置
                if (taskInfo.getTaskClass() == null) {
                    Task task = taskService.selectTaskById(taskInfo.getTaskid());
                    if (task != null) {
                        taskInfo.setTaskClass(task.getTaskClass());
                    } else {
                        // 默认为团队任务
                        taskInfo.setTaskClass(0);
                    }
                }
                result.add(taskInfo);
            }
        }

        // 模糊查询：按任务名
        if (taskname != null && !taskname.isEmpty()) {
            result = result.stream()
                    .filter(item -> item.getTaskname().contains(taskname))
                    .collect(Collectors.toList());
        }

        // 特定任务ID过滤
        if (taskid != null) {
            result = result.stream()
                    .filter(item -> taskid.equals(item.getTaskid()))
                    .collect(Collectors.toList());
        }

        List<Mark> marks = new ArrayList<>();
        if (taskid != null) {
            marks = markService.getMarkByTaskId(taskid);
        }

        // 计算起始索引和结束索引，实现分页
        int startIndex = (current - 1) * pageSize;
        int endIndex = Math.min(startIndex + pageSize, result.size());

        // 防止索引越界
        if (startIndex < result.size()) {
            result = result.subList(startIndex, endIndex);
        } else {
            result = new ArrayList<>();
        }

        Map<String, Object> response = new HashMap<>();
        response.put("code", 200);
        response.put("data", result);
        response.put("success", true);
        response.put("markGeoJsonArr", convertGeojson(marks));
        response.put("total", taskCount);
        return response;
    }

    @GetMapping("/getMarkTaskDetail")
    @ApiOperation("获取标注页面所需的任务详情，专用于标注界面")
    public Map<String, Object> getMarkTaskDetail(@RequestParam Integer taskid) {
        // 获取当前登录用户信息
        LoginUser loginUser = (LoginUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        SysUser currentUser = loginUser.getSysUser();
        String username = currentUser.getUsername();
        Integer userId = currentUser.getUserid();
        
        // 获取任务详情
        Task task = taskService.selectTaskById(taskid);
        if (task == null) {
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("code", 400);
            errorResponse.put("message", "任务不存在");
            return errorResponse;
        }
        
        // 创建标准化的任务信息对象
        TaskInfoDTO taskInfo = new TaskInfoDTO();
        taskInfo.setTaskid(task.getTaskId());
        taskInfo.setTaskname(task.getTaskName());
        taskInfo.setType(task.getTaskType());
        taskInfo.setMapserver(task.getMapServer());
        taskInfo.setDaterange(task.getDateRange());
        taskInfo.setStatus(task.getStatus());
        taskInfo.setAuditfeedback(task.getAuditFeedback());
        taskInfo.setTaskClass(task.getTaskClass());
        
        // 获取与该任务关联的用户信息
        List<Map<String, Object>> userArrOrigin = new ArrayList<>();
        List<String> usernames = taskService.findUserListByTaskId(taskid);
        
        for (String user : usernames) {
            SysUser userObj = sysUserService.findByUsername(user);
            if (userObj != null) {
                // 获取分配给该用户的类型
                String typeString = taskAcceptedService.getTypeArrByTaskIdAndUsername(taskid, user);
                List<Type> typeArr = new ArrayList<>();
                
                if (typeString != null && !typeString.isEmpty()) {
                    List<Integer> typeIds = Arrays.stream(typeString.split(","))
                            .map(Integer::parseInt)
                            .collect(Collectors.toList());
                    
                    for (Integer typeId : typeIds) {
                        String typeName = typeService.getTypeNameById(typeId);
                        List<Type> types = typeService.getTypes(1, 100, typeId, typeName);
                        if (!types.isEmpty()) {
                            typeArr.add(types.get(0));
                        }
                    }
                }
                
                Map<String, Object> info = new HashMap<>();
                info.put("userid", userObj.getUserid());
                info.put("username", userObj.getUsername());
                info.put("typeArr", typeArr);
                userArrOrigin.add(info);
            }
        }
        
        taskInfo.setUserArr(userArrOrigin);
        
        // 获取标注数据
        List<Mark> marks = markService.getMarkByTaskId(taskid);
        
        // 构建响应
        Map<String, Object> response = new HashMap<>();
        List<TaskInfoDTO> resultList = new ArrayList<>();
        resultList.add(taskInfo);
        
        response.put("code", 200);
        response.put("data", resultList);
        response.put("success", true);
        response.put("markGeoJsonArr", convertGeojson(marks));
        return response;
    }
}
