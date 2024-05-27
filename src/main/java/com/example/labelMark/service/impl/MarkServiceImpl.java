package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.mapper.MarkMapper;
import com.example.labelMark.service.MarkService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
@Service
public class MarkServiceImpl extends ServiceImpl<MarkMapper, Mark> implements MarkService {

    @Resource
    private MarkMapper markMapper;

    @Override
    public boolean isMark(int taskId, int userId) {
        int count = markMapper.isMark(taskId, userId);
        if(count != 0){
            return true;
        }else {
            return false;
        }
    }

    @Override
    public void createMark(int taskId, int userId, int typeId, String geom) {
        markMapper.createMark(taskId, userId, typeId, geom);
    }

    @Override
    public void deleteMark(int taskId, int userId,int typeId) {
        markMapper.deleteMark(taskId, userId, typeId);
    }

    @Override
    public void insertMark(Mark mark) {
        save(mark);
//        markMapper.insertMark(mark);
    }

    @Override
    public void deleteMarkByTaskId(int taskId) {
        markMapper.deleteMarkByTaskId(taskId);
    }

    @Override
    public long GetTaskIdNum(int taskId) {
//        Integer num = markMapper.GetTaskIdNum(taskId);
        QueryWrapper<Mark> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("task_id", taskId);
        long count = count(queryWrapper);
        return count;
    }

    @Override
    public List<Mark> getMarkByTaskId(Integer taskId) {
        QueryWrapper<Mark> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("task_id", taskId);
        return list(queryWrapper);
    }
}
