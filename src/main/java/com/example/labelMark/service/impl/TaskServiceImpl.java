package com.example.labelMark.service.impl;

import com.example.labelMark.domain.Task;
import com.example.labelMark.mapper.TaskMapper;
import com.example.labelMark.service.TaskService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
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
    public void createTask(Task task) {
        taskMapper.insert(task);
    }

    @Override
    public List<Map<String, Object>> getTaskInfo() {
        List<Map<String, Object>> list = taskMapper.getTaskInfo();
        return list;
    }

    @Override
    public List<Integer> getIDs() {
        List<Integer> IDs = taskMapper.getIDs();
        return IDs;
    }

    @Override
    public void updateTaskById(int taskId, String taskName, String dataRange, String taskType, String mapServer) {

        taskMapper.updateTaskById(taskId, taskName, dataRange, taskType, mapServer);
    }

    @Override
    public void deleteTaskById(int taskId) {
        taskMapper.deleteById(taskId);
    }

    @Override
    public List<Task> selectTaskById(int taskId) {
        List<Task> tasks = taskMapper.selectTaskById(taskId);
        return tasks;
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
    public  List<Map<String, Object>> findAllTask() {
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
    public void updateTask(int taskId, int Id) {
        taskMapper.updateTask(taskId, Id);
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


}
