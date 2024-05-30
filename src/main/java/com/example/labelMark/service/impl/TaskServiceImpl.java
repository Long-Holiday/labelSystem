package com.example.labelMark.service.impl;

import cn.hutool.core.util.ObjectUtil;
import com.example.labelMark.domain.Task;
import com.example.labelMark.mapper.TaskMapper;
import com.example.labelMark.service.TaskService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.labelMark.vo.TaskInfoDTO;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Service
public class TaskServiceImpl extends ServiceImpl<TaskMapper, Task> implements TaskService {

    @Resource
    private TaskMapper taskMapper;

    @Override
    public int createTask(String dataRange, String taskName, String taskType
            , String mapServer) {
        Task task = new Task();
//        初试状态为未提交
        task.setStatus(3);
        task.setDateRange(dataRange);
        task.setTaskName(taskName);
        task.setTaskType(taskType);
        task.setMapServer(mapServer);
        boolean isSaved = save(task);
//        taskMapper.insert(task);
        return isSaved == true ? task.getTaskId() : -1;
    }

    @Override
    public List<TaskInfoDTO> getTaskInfo(String username) {
        List<Map<String, Object>> list = taskMapper.getTaskInfo(username);
        List<TaskInfoDTO> taskInfoDTOList = new ArrayList<>();
        for (Map<String, Object> map : list) {
            TaskInfoDTO taskInfoDTO = new TaskInfoDTO();
            if (ObjectUtil.isNotNull(map.get("task_id"))) {
                taskInfoDTO.setTaskid((Integer) map.get("task_id"));
            }
            if (ObjectUtil.isNotNull(map.get("task_name"))) {
                taskInfoDTO.setTaskname((String) map.get("task_name"));
            }
            if (ObjectUtil.isNotNull(map.get("id"))) {
                taskInfoDTO.setId((Integer) map.get("id"));
            }
            if (ObjectUtil.isNotNull(map.get("task_type"))) {
                taskInfoDTO.setType((String) map.get("task_type"));
            }
            if (ObjectUtil.isNotNull(map.get("map_server"))) {
                taskInfoDTO.setMapserver((String) map.get("map_server"));
            }
            if (ObjectUtil.isNotNull(map.get("date_range"))) {
                taskInfoDTO.setDaterange((String) map.get("date_range"));
            }
            if (ObjectUtil.isNotNull(map.get("status"))) {
                taskInfoDTO.setStatus((Integer) map.get("status"));
            }
            if (ObjectUtil.isNotNull(map.get("userid"))) {
                taskInfoDTO.setUserid((Integer) map.get("userid"));
            }
            if (ObjectUtil.isNotNull(map.get("username"))) {
                taskInfoDTO.setUsername((String) map.get("username"));
            }
            if (ObjectUtil.isNotNull(map.get("type_arr"))) {
                taskInfoDTO.setTypeArr((String) map.get("type_arr"));
            }
            taskInfoDTOList.add(taskInfoDTO);
        }
        return taskInfoDTOList;
    }

    @Override
    public List<Integer> getIDs() {
        List<Integer> IDs = taskMapper.getIDs();
        return IDs;
    }

    @Override
    public void updateTaskById(int taskId, String taskName, String dateRange, String taskType, String mapServer) {

        taskMapper.updateTaskById(taskId, taskName, dateRange, taskType, mapServer);
    }

    @Override
    public void deleteTaskById(int taskId) {
        taskMapper.deleteById(taskId);
    }

    @Override
    public Task selectTaskById(int taskId) {
        Task task = taskMapper.selectTaskById(taskId);
        return task;
    }

    @Override
    public void updateTaskStatus(int taskId) {
        taskMapper.updateTaskStatus(taskId);
    }

    @Override
    public void auditTask(int taskId, int status, String auditFeedback) {
        taskMapper.auditTask(taskId, status, auditFeedback);
    }

    @Override
    public int getTotalTasks() {
        return (int) count();
    }

    @Override
    public List<Map<String, Object>> findAllTask() {
        System.out.println(231);
        List<Map<String, Object>> taskDatasetInfos = taskMapper.findAllTask();
        System.out.println(taskDatasetInfos);
        return taskDatasetInfos;
    }

    @Override
    public List<Map<String, Object>> findPublicTask() {
        List<Map<String, Object>> taskDatasetInfos = taskMapper.findPublicTask();
        return taskDatasetInfos;
    }

    @Override
    public List<Map<String, Object>> findTasksByUsername(String username) {
        List<Map<String, Object>> taskAccepted = taskMapper.findTasksByUsername(username);
        return taskAccepted;
    }

    @Override
    public List<String> findUserListByTaskId(int taskId) {
        List<String> usernameList = taskMapper.findUserListByTaskId(taskId);
        return usernameList;
    }

    @Override
    public void updateTask(int taskId, String markIdStr) {
        taskMapper.updateTask(taskId, markIdStr);
    }

    @Override
    public String getServerById(int taskId) {
        String serverName = taskMapper.getServerById(taskId);
        return serverName;
    }

    @Override
    public String getTypeById(int taskId) {
        String taskType = taskMapper.getTypeById(taskId);
        return taskType;
    }

    @Override
    public String getMarkIdById(int taskId) {
        Task task = getById(taskId);
        return ObjectUtil.isNotNull(task) && task.getMarkId() != null ? task.getMarkId() : null;
    }


}
