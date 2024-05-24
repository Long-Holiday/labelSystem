package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.example.labelMark.domain.SysFile;
import com.example.labelMark.mapper.SysFileMapper;
import com.example.labelMark.service.SysFileService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@Service
public class SysFileServiceImpl extends ServiceImpl<SysFileMapper, SysFile> implements SysFileService {

    @Resource
    private SysFileMapper sysfileMapper;

    @Override
    public List<SysFile> getAllFiles(Integer current, Integer pageSize, Integer fileId) {
        int offset = pageSize * (current - 1);
        List<SysFile> SysFiles = sysfileMapper.getAllFiles(current, pageSize, fileId, offset);
        return SysFiles;
    }

    @Override
    public void updateFile(Integer fileId, String fileName, String updateTime) {
        sysfileMapper.updateFile(fileId, fileName, updateTime);
    }

    @Override
    public void deleteFile(String fileName) {
        QueryWrapper<SysFile> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("file_name", fileName);
        sysfileMapper.delete(queryWrapper);

    }

    @Override
    public void createFile(String fileName, String updateTime, String size) {
        sysfileMapper.createFile(fileName, updateTime, size);
    }

    @Override
    public boolean updateFileStatus(String fileName) {
        UpdateWrapper<SysFile> wrapper = new UpdateWrapper<>();
        wrapper.eq("file_name", fileName).set("status", 1);
        boolean update = update(null, wrapper);
        return update;
    }
}
